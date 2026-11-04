<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen && backlogItem" class="modal-overlay" @click="close">
        <div class="modal-container" role="dialog" aria-modal="true" aria-labelledby="po-modal-title" @click.stop>
          <div class="modal-header">
            <h3 id="po-modal-title" class="modal-title">
              {{ mode === 'view' ? t('purchaseOrder.viewTitle') : t('purchaseOrder.createTitle') }}
            </h3>
            <button class="close-button" :aria-label="t('common.close')" @click="close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <div class="info-grid summary">
              <div class="info-item">
                <div class="info-label">{{ t('purchaseOrder.orderId') }}</div>
                <div class="info-value mono">{{ backlogItem.order_id }}</div>
              </div>
              <div class="info-item">
                <div class="info-label">{{ t('purchaseOrder.sku') }}</div>
                <div class="info-value mono">{{ backlogItem.item_sku }}</div>
              </div>
              <div class="info-item">
                <div class="info-label">{{ t('purchaseOrder.itemName') }}</div>
                <div class="info-value">{{ translateProductName(backlogItem.item_name) }}</div>
              </div>
            </div>

            <!-- View mode -->
            <template v-if="mode === 'view'">
              <div v-if="loading" class="state-msg">{{ t('common.loading') }}</div>
              <div v-else-if="error" class="form-error" role="alert">{{ error }}</div>
              <div v-else-if="po" class="info-grid">
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.poId') }}</div>
                  <div class="info-value mono">{{ po.id }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.status') }}</div>
                  <div class="info-value">{{ po.status }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.supplier') }}</div>
                  <div class="info-value">{{ po.supplier_name }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.quantity') }}</div>
                  <div class="info-value">{{ po.quantity }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.unitCost') }}</div>
                  <div class="info-value">{{ formatCurrencyWithDecimals(po.unit_cost, currentCurrency, 2) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.total') }}</div>
                  <div class="info-value">{{ formatCurrency(po.quantity * po.unit_cost, currentCurrency) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.expectedDelivery') }}</div>
                  <div class="info-value">{{ po.expected_delivery_date }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.createdDate') }}</div>
                  <div class="info-value">{{ po.created_date }}</div>
                </div>
                <div v-if="po.notes" class="info-item full">
                  <div class="info-label">{{ t('purchaseOrder.notes') }}</div>
                  <div class="info-value">{{ po.notes }}</div>
                </div>
              </div>
            </template>

            <!-- Create mode -->
            <form v-else id="po-form" class="form-grid" @submit.prevent="submit">
              <div class="field full">
                <label for="po-supplier">{{ t('purchaseOrder.supplier') }}</label>
                <input id="po-supplier" v-model.trim="form.supplier_name" type="text" maxlength="200" required />
              </div>
              <div class="field">
                <label for="po-quantity">{{ t('purchaseOrder.quantity') }}</label>
                <input id="po-quantity" v-model.number="form.quantity" type="number" min="1" step="1" required />
              </div>
              <div class="field">
                <label for="po-cost">{{ t('purchaseOrder.unitCostUsd') }}</label>
                <input id="po-cost" v-model.number="form.unit_cost" type="number" min="0.01" step="0.01" required />
              </div>
              <div class="field full">
                <label for="po-date">{{ t('purchaseOrder.expectedDelivery') }}</label>
                <input id="po-date" v-model="form.expected_delivery_date" type="date" required />
              </div>
              <div class="field full">
                <label for="po-notes">{{ t('purchaseOrder.notesOptional') }}</label>
                <textarea id="po-notes" v-model="form.notes" rows="3" maxlength="1000"></textarea>
              </div>
              <div v-if="error" class="form-error full" role="alert">{{ error }}</div>
            </form>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn-secondary" @click="close">{{ t('common.close') }}</button>
            <button
              v-if="mode === 'create'"
              type="submit"
              form="po-form"
              class="btn-primary"
              :disabled="!isValid || submitting"
            >
              {{ submitting ? t('purchaseOrder.submitting') : t('purchaseOrder.submit') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'

const { t, currentCurrency, translateProductName } = useI18n()

const props = defineProps({
  isOpen: { type: Boolean, default: false },
  backlogItem: { type: Object, default: null },
  mode: { type: String, default: 'create' }
})

const emit = defineEmits(['close', 'po-created'])

const emptyForm = () => ({
  supplier_name: '',
  quantity: Math.max(1, (props.backlogItem?.quantity_needed ?? 0) - (props.backlogItem?.quantity_available ?? 0)),
  unit_cost: null,
  expected_delivery_date: '',
  notes: ''
})

const form = ref(emptyForm())
const po = ref(null)
const loading = ref(false)
const submitting = ref(false)
const error = ref(null)

// Mirrors the server's validation so the submit button reflects what the API will accept.
const isValid = computed(() => {
  const f = form.value
  return f.supplier_name.length >= 1 && f.supplier_name.length <= 200 &&
    Number.isInteger(f.quantity) && f.quantity > 0 &&
    typeof f.unit_cost === 'number' && f.unit_cost > 0 &&
    /^\d{4}-\d{2}-\d{2}$/.test(f.expected_delivery_date) &&
    f.notes.length <= 1000
})

// FastAPI returns `detail` as a string (HTTPException) or a list of objects (422 validation).
const errorMessage = (err, fallback) => {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(d => d.msg).join('; ')
  return fallback
}

const loadPO = async () => {
  loading.value = true
  try {
    po.value = await api.getPurchaseOrderByBacklogItem(props.backlogItem.id)
  } catch (err) {
    console.error(err)
    error.value = errorMessage(err, t('purchaseOrder.loadError'))
  } finally {
    loading.value = false
  }
}

// Reset all state on every open; the item is read at open time so the default quantity matches it.
watch(() => props.isOpen, (open) => {
  if (!open || !props.backlogItem) return
  form.value = emptyForm()
  po.value = null
  error.value = null
  submitting.value = false
  loading.value = false
  if (props.mode === 'view') loadPO()
})

const submit = async () => {
  if (!isValid.value || submitting.value) return
  submitting.value = true
  error.value = null
  try {
    const created = await api.createPurchaseOrder({
      backlog_item_id: props.backlogItem.id,
      supplier_name: form.value.supplier_name,
      quantity: form.value.quantity,
      unit_cost: form.value.unit_cost,
      expected_delivery_date: form.value.expected_delivery_date,
      notes: form.value.notes
    })
    emit('po-created', created)
  } catch (err) {
    console.error(err)
    error.value = errorMessage(err, t('purchaseOrder.createError'))
  } finally {
    submitting.value = false
  }
}

const close = () => emit('close')

const onKeydown = (e) => {
  if (e.key === 'Escape' && props.isOpen) close()
}
onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.close-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.close-button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1.5rem;
}

.info-grid.summary {
  padding-bottom: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 1.5rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-width: 0;
}

.info-item.full,
.field.full,
.form-error.full {
  grid-column: 1 / -1;
}

.info-label,
.field label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.info-value {
  font-size: 0.938rem;
  color: #0f172a;
  font-weight: 500;
  overflow-wrap: anywhere;
}

.info-value.mono {
  font-family: 'Monaco', 'Courier New', monospace;
  color: #2563eb;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.25rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.field input,
.field textarea {
  padding: 0.625rem 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.875rem;
  font-family: inherit;
  color: #0f172a;
  resize: vertical;
}

.field input:focus,
.field textarea:focus {
  outline: 2px solid #0f172a;
  outline-offset: 1px;
}

.state-msg {
  color: #64748b;
  font-size: 0.875rem;
}

.form-error {
  padding: 0.75rem 1rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #991b1b;
  font-size: 0.875rem;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-secondary,
.btn-primary {
  padding: 0.625rem 1.25rem;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-secondary {
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  color: #334155;
}

.btn-secondary:hover {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.btn-primary {
  background: #0f172a;
  border: 1px solid #0f172a;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #1e293b;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Modal transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
