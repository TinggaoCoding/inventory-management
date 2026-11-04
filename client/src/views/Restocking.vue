<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <label for="budget" class="budget-label">
          {{ t('restocking.budget') }}: <strong>{{ currencySymbol }}{{ budget.toLocaleString() }}</strong>
        </label>
        <input id="budget" v-model.number="budget" type="range" min="0" :max="maxBudget" step="500" class="budget-slider" />
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.budget') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ budget.toLocaleString() }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.recommendedTotal') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ recommendedTotal.toLocaleString() }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.remaining') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ remaining.toLocaleString() }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.itemsSelected') }}</div>
          <div class="stat-value">{{ recommended.length }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendedItems') }}</h3>
          <button class="place-order" :disabled="!recommended.length || submitting || !!placedOrder" @click="placeOrder">
            {{ submitting ? t('restocking.placing') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="submitError" class="error" role="alert">{{ submitError }}</div>
        <div v-if="placedOrder" class="confirmation" role="status">
          {{ t('restocking.orderPlaced', { orderNumber: placedOrder.order_number }) }}
          <router-link to="/orders">{{ t('restocking.viewOrders') }}</router-link>
        </div>

        <div v-if="!recommended.length" class="empty">{{ t('restocking.empty') }}</div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineCost') }}</th>
                <th>{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="line in recommended" :key="line.item_sku">
                <td><strong>{{ line.item_sku }}</strong></td>
                <td>{{ translateProductName(line.item_name) }}</td>
                <td><span :class="['badge', line.trend]">{{ t(`trends.${line.trend}`) }}</span></td>
                <td>{{ line.quantity }}</td>
                <td>{{ currencySymbol }}{{ line.unit_cost.toLocaleString() }}</td>
                <td><strong>{{ currencySymbol }}{{ line.cost.toLocaleString() }}</strong></td>
                <td>{{ line.lead_time_days }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

const STEP = 500
const TREND_RANK = { increasing: 0, stable: 1, decreasing: 2 }

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName } = useI18n()
    const currencySymbol = computed(() => (currentCurrency.value === 'JPY' ? '¥' : '$'))

    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])
    const budget = ref(0)
    const submitting = ref(false)
    const submitError = ref(null)
    const placedOrder = ref(null)

    // One line per forecast: a 30-day supply (forecasted_demand units) at the server-set unit cost
    const lines = computed(() =>
      forecasts.value.map(f => ({
        ...f,
        quantity: f.forecasted_demand,
        // Round to cents like the server's total_cost, so float drift can't flip a fits/doesn't-fit check
        cost: Math.round(f.forecasted_demand * f.unit_cost * 100) / 100,
        growth: f.current_demand > 0 ? (f.forecasted_demand - f.current_demand) / f.current_demand : 0
      }))
    )

    // Round up to the slider step so the top of the range covers every line
    const maxBudget = computed(() => Math.ceil(lines.value.reduce((sum, l) => sum + l.cost, 0) / STEP) * STEP)

    const recommended = computed(() => {
      // Rank by trend (increasing > stable > decreasing), then by growth % descending within a trend.
      const ranked = [...lines.value].sort(
        (a, b) => (TREND_RANK[a.trend] ?? 3) - (TREND_RANK[b.trend] ?? 3) || b.growth - a.growth
      )
      // Greedy fill: take each line that still fits the remaining budget; a line that
      // doesn't fit is skipped (not a stop), so cheaper lower-ranked lines can still be added.
      let left = budget.value
      const picked = []
      for (const line of ranked) {
        if (line.cost <= left) {
          picked.push(line)
          left -= line.cost
        }
      }
      return picked
    })

    const recommendedTotal = computed(() => recommended.value.reduce((sum, l) => sum + l.cost, 0))
    const remaining = computed(() => budget.value - recommendedTotal.value)

    const loadForecasts = async () => {
      try {
        loading.value = true
        forecasts.value = await api.getDemandForecasts()
        // Default to roughly half the max, rounded to the slider step
        budget.value = Math.round(maxBudget.value / 2 / STEP) * STEP
      } catch (err) {
        error.value = 'Failed to load demand forecasts: ' + err.message
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      submitting.value = true
      submitError.value = null
      placedOrder.value = null
      try {
        placedOrder.value = await api.createRestockOrder(
          recommended.value.map(r => ({ sku: r.item_sku, quantity: r.quantity }))
        )
      } catch (err) {
        // Keep the current selection so the user can retry. FastAPI sends a string detail for
        // 400s but an array of validation errors for 422s, so only show it when it's a string.
        const detail = err.response?.data?.detail
        submitError.value = typeof detail === 'string' ? detail : err.message
      } finally {
        submitting.value = false
      }
    }

    // The button stays disabled after a successful order so a second click can't submit a duplicate;
    // changing the budget means a new selection, so clear the confirmation and re-enable it.
    watch(budget, () => {
      placedOrder.value = null
    })

    onMounted(loadForecasts)

    return {
      t,
      currencySymbol,
      translateProductName,
      loading,
      error,
      budget,
      maxBudget,
      recommended,
      recommendedTotal,
      remaining,
      submitting,
      submitError,
      placedOrder,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.5rem;
}

.budget-label {
  display: block;
  margin-bottom: 0.75rem;
  color: #64748b;
  font-size: 0.875rem;
}

.budget-label strong {
  color: #0f172a;
}

.budget-slider {
  width: 100%;
}

.place-order {
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1rem;
  font-weight: 600;
  cursor: pointer;
}

.place-order:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.confirmation {
  margin: 0 1.5rem 1rem;
  padding: 0.75rem 1rem;
  background: #d1fae5;
  border: 1px solid #10b981;
  border-radius: 6px;
  color: #065f46;
}

.confirmation a {
  margin-left: 0.75rem;
  font-weight: 600;
}

.empty {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}
</style>
