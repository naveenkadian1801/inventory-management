<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <!-- Budget Slider Card -->
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">{{ t('restocking.budget') }}</h3>
        <span class="budget-display">{{ currencySymbol }}{{ budget.toLocaleString() }}</span>
      </div>
      <div class="slider-wrapper">
        <span class="slider-bound">{{ currencySymbol }}1,000</span>
        <input
          type="range"
          class="budget-slider"
          min="1000"
          max="50000"
          step="1000"
          v-model.number="budget"
        />
        <span class="slider-bound">{{ currencySymbol }}50,000</span>
      </div>
      <p class="slider-hint">{{ t('restocking.budgetSlider') }}</p>
    </div>

    <!-- Loading / Error / Content -->
    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <!-- Recommendations Table Card -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }}</h3>
          <div class="header-actions">
            <button class="btn-link" @click="selectAll">{{ t('restocking.selectAll') }}</button>
            <span class="separator">|</span>
            <button class="btn-link" @click="deselectAll">{{ t('restocking.deselectAll') }}</button>
          </div>
        </div>

        <div v-if="recommendations.length === 0" class="empty-state">
          {{ t('restocking.noRecommendations') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.select') }}</th>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.currentDemand') }}</th>
                <th>{{ t('restocking.table.forecastedDemand') }}</th>
                <th>{{ t('restocking.table.growth') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.lineCost') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in recommendations"
                :key="item.item_sku"
                :class="{ 'row-deselected': !selectedSkus.has(item.item_sku) }"
              >
                <td>
                  <input
                    type="checkbox"
                    class="row-checkbox"
                    :checked="selectedSkus.has(item.item_sku)"
                    @change="toggleSelection(item.item_sku)"
                  />
                </td>
                <td><strong>{{ item.item_sku }}</strong></td>
                <td>{{ item.item_name }}</td>
                <td>{{ item.current_demand }}</td>
                <td><strong>{{ item.forecasted_demand }}</strong></td>
                <td>
                  <span class="badge increasing">+{{ item.demand_growth }}%</span>
                </td>
                <td>{{ currencySymbol }}{{ item.unit_cost.toLocaleString() }}</td>
                <td>
                  <input
                    type="number"
                    class="qty-input"
                    :min="1"
                    :max="item.demand_growth"
                    :value="getQuantity(item.item_sku, item)"
                    :disabled="!selectedSkus.has(item.item_sku)"
                    @change="updateQuantity(item.item_sku, $event.target.value, item)"
                  />
                </td>
                <td class="line-cost">
                  {{ selectedSkus.has(item.item_sku)
                    ? `${currencySymbol}${getLineCost(item.item_sku, item).toLocaleString()}`
                    : '—'
                  }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Summary Bar -->
      <div class="summary-bar" :class="{ 'over-budget': isOverBudget }">
        <div class="summary-left">
          <div class="summary-stat">
            <span class="summary-label">{{ t('restocking.summary.totalCost') }}</span>
            <span class="summary-value" :class="{ 'over-budget-text': isOverBudget }">
              {{ currencySymbol }}{{ totalCost.toLocaleString() }}
            </span>
          </div>
          <div class="summary-stat">
            <span class="summary-label">{{ t('restocking.summary.ofBudget') }}</span>
            <span class="summary-value" :class="{ 'over-budget-text': isOverBudget }">
              {{ budgetPercent }}%
            </span>
          </div>
          <div class="budget-bar-track">
            <div
              class="budget-bar-fill"
              :class="{ 'over-budget-fill': isOverBudget }"
              :style="{ width: Math.min(budgetPercent, 100) + '%' }"
            ></div>
          </div>
        </div>
        <div class="summary-right">
          <span v-if="selectedSkus.size === 0" class="no-items-note">
            {{ t('restocking.summary.noItems') }}
          </span>
          <button
            class="btn-primary"
            :disabled="selectedSkus.size === 0 || isOverBudget || placing"
            @click="placeOrder"
          >
            {{ placing ? t('common.loading') : t('restocking.summary.placeOrder') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Success Toast -->
    <transition name="toast">
      <div v-if="toastVisible" class="toast toast-success">
        <span class="toast-icon">&#10003;</span>
        <div class="toast-body">
          <strong>{{ t('restocking.toast.success') }}</strong>
          <span>{{ t('restocking.toast.orderNumber') }} {{ toastOrderNumber }}</span>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency } = useI18n()
    const { selectedLocation, selectedCategory, getCurrentFilters } = useFilters()

    // Budget state
    const budget = ref(10000)

    // Recommendations data
    const recommendations = ref([])
    const loading = ref(false)
    const error = ref(null)

    // Selection state: Set of selected SKUs
    const selectedSkus = ref(new Set())

    // Quantity overrides: Map of sku -> quantity
    const quantities = ref({})

    // Order placement state
    const placing = ref(false)

    // Toast state
    const toastVisible = ref(false)
    const toastOrderNumber = ref('')
    let toastTimer = null

    // Currency symbol derived from current locale
    const currencySymbol = computed(() => {
      return currentCurrency.value === 'JPY' ? '¥' : '$'
    })

    // --- Data loading ---

    const loadRecommendations = async () => {
      loading.value = true
      error.value = null
      try {
        const filters = getCurrentFilters()
        const data = await api.getRestockRecommendations(budget.value, filters)
        recommendations.value = data.recommendations || []

        // Pre-select all items and reset quantities to recommended defaults
        const newSelected = new Set()
        const newQtys = {}
        recommendations.value.forEach(item => {
          newSelected.add(item.item_sku)
          // Use recommended_quantity if provided, else fall back to demand_growth
          newQtys[item.item_sku] = item.recommended_quantity ?? item.demand_growth
        })
        selectedSkus.value = newSelected
        quantities.value = newQtys
      } catch (err) {
        error.value = 'Failed to load restock recommendations'
        console.error(err)
      } finally {
        loading.value = false
      }
    }

    // --- Selection helpers ---

    const toggleSelection = (sku) => {
      const next = new Set(selectedSkus.value)
      if (next.has(sku)) {
        next.delete(sku)
      } else {
        next.add(sku)
      }
      selectedSkus.value = next
    }

    const selectAll = () => {
      selectedSkus.value = new Set(recommendations.value.map(i => i.item_sku))
    }

    const deselectAll = () => {
      selectedSkus.value = new Set()
    }

    // --- Quantity helpers ---

    const getQuantity = (sku, item) => {
      if (quantities.value[sku] !== undefined) return quantities.value[sku]
      return item.recommended_quantity ?? item.demand_growth
    }

    const updateQuantity = (sku, rawValue, item) => {
      const parsed = parseInt(rawValue, 10)
      const max = item.demand_growth
      if (isNaN(parsed) || parsed < 1) {
        quantities.value = { ...quantities.value, [sku]: 1 }
      } else if (parsed > max) {
        quantities.value = { ...quantities.value, [sku]: max }
      } else {
        quantities.value = { ...quantities.value, [sku]: parsed }
      }
    }

    // --- Cost computations ---

    const getLineCost = (sku, item) => {
      const qty = getQuantity(sku, item)
      return qty * item.unit_cost
    }

    const totalCost = computed(() => {
      return recommendations.value
        .filter(item => selectedSkus.value.has(item.item_sku))
        .reduce((sum, item) => sum + getLineCost(item.item_sku, item), 0)
    })

    const budgetPercent = computed(() => {
      if (budget.value === 0) return 0
      return Math.round((totalCost.value / budget.value) * 100)
    })

    const isOverBudget = computed(() => totalCost.value > budget.value)

    // --- Order placement ---

    const placeOrder = async () => {
      if (selectedSkus.value.size === 0 || isOverBudget.value || placing.value) return

      placing.value = true
      try {
        const items = recommendations.value
          .filter(item => selectedSkus.value.has(item.item_sku))
          .map(item => ({
            sku: item.item_sku,
            name: item.item_name,
            quantity: getQuantity(item.item_sku, item),
            unit_price: item.unit_cost
          }))

        // Use selected warehouse, defaulting to "San Francisco"
        const warehouse =
          selectedLocation.value !== 'all' ? selectedLocation.value : 'San Francisco'

        const result = await api.placeRestockOrder({ items, warehouse })

        // Show success toast
        toastOrderNumber.value = result.order_number || result.id || ''
        showToast()

        // Reload recommendations after order is placed
        await loadRecommendations()
      } catch (err) {
        error.value = 'Failed to place restock order'
        console.error(err)
      } finally {
        placing.value = false
      }
    }

    const showToast = () => {
      toastVisible.value = true
      if (toastTimer) clearTimeout(toastTimer)
      toastTimer = setTimeout(() => {
        toastVisible.value = false
      }, 4000)
    }

    // --- Watchers ---

    // Reload when budget changes (debounced via watcher on the value directly)
    watch(budget, () => {
      loadRecommendations()
    })

    // Reload when warehouse/category filters change
    watch([selectedLocation, selectedCategory], () => {
      loadRecommendations()
    })

    onMounted(() => loadRecommendations())

    return {
      t,
      budget,
      currencySymbol,
      recommendations,
      loading,
      error,
      selectedSkus,
      quantities,
      placing,
      toastVisible,
      toastOrderNumber,
      totalCost,
      budgetPercent,
      isOverBudget,
      toggleSelection,
      selectAll,
      deselectAll,
      getQuantity,
      updateQuantity,
      getLineCost,
      placeOrder
    }
  }
}
</script>

<style scoped>
/* Budget slider card */
.budget-display {
  font-size: 1.5rem;
  font-weight: 700;
  color: #2563eb;
  letter-spacing: -0.025em;
}

.slider-wrapper {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin: 0.75rem 0 0.5rem;
}

.slider-bound {
  font-size: 0.813rem;
  color: #64748b;
  font-weight: 500;
  white-space: nowrap;
}

.budget-slider {
  flex: 1;
  height: 6px;
  -webkit-appearance: none;
  appearance: none;
  background: #e2e8f0;
  border-radius: 3px;
  outline: none;
  cursor: pointer;
  accent-color: #2563eb;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #2563eb;
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(37, 99, 235, 0.4);
  transition: box-shadow 0.2s;
}

.budget-slider::-webkit-slider-thumb:hover {
  box-shadow: 0 1px 8px rgba(37, 99, 235, 0.6);
}

.slider-hint {
  font-size: 0.813rem;
  color: #94a3b8;
}

/* Table header actions */
.header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-link {
  background: none;
  border: none;
  color: #2563eb;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.btn-link:hover {
  color: #1d4ed8;
}

.separator {
  color: #cbd5e1;
  font-size: 0.875rem;
}

/* Table row states */
.row-deselected td {
  color: #94a3b8;
}

.row-checkbox {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: #2563eb;
}

/* Quantity input */
.qty-input {
  width: 70px;
  padding: 0.25rem 0.5rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.875rem;
  color: #0f172a;
  background: #f8fafc;
  text-align: center;
  transition: border-color 0.15s;
}

.qty-input:focus {
  outline: none;
  border-color: #2563eb;
  background: #fff;
}

.qty-input:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  background: #f1f5f9;
}

/* Remove number input spinners */
.qty-input::-webkit-inner-spin-button,
.qty-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.line-cost {
  font-weight: 600;
  color: #0f172a;
}

/* Empty state */
.empty-state {
  padding: 3rem;
  text-align: center;
  color: #64748b;
  font-size: 0.938rem;
}

/* Summary bar */
.summary-bar {
  position: sticky;
  bottom: 0;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 1rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 2rem;
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.06);
  margin-top: 0.5rem;
}

.summary-bar.over-budget {
  border-color: #fca5a5;
  background: #fff9f9;
}

.summary-left {
  display: flex;
  align-items: center;
  gap: 2rem;
  flex: 1;
}

.summary-stat {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.summary-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.summary-value {
  font-size: 1.375rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.summary-value.over-budget-text {
  color: #dc2626;
}

.budget-bar-track {
  flex: 1;
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
  min-width: 80px;
}

.budget-bar-fill {
  height: 100%;
  background: #059669;
  border-radius: 4px;
  transition: width 0.3s ease, background 0.3s ease;
}

.budget-bar-fill.over-budget-fill {
  background: #dc2626;
}

.summary-right {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-shrink: 0;
}

.no-items-note {
  font-size: 0.875rem;
  color: #94a3b8;
  font-style: italic;
}

.btn-primary {
  background: #2563eb;
  color: #ffffff;
  border: none;
  border-radius: 8px;
  padding: 0.625rem 1.5rem;
  font-size: 0.938rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, box-shadow 0.2s;
  white-space: nowrap;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.35);
}

.btn-primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* Success toast */
.toast {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  display: flex;
  align-items: flex-start;
  gap: 0.875rem;
  background: #ffffff;
  border: 1px solid #a7f3d0;
  border-left: 4px solid #059669;
  border-radius: 10px;
  padding: 1rem 1.25rem;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  z-index: 1000;
  min-width: 260px;
  max-width: 360px;
}

.toast-icon {
  font-size: 1.125rem;
  color: #059669;
  font-weight: 700;
  line-height: 1.4;
  flex-shrink: 0;
}

.toast-body {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.toast-body strong {
  font-size: 0.938rem;
  color: #065f46;
}

.toast-body span {
  font-size: 0.813rem;
  color: #64748b;
}

/* Toast transition */
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
</style>
