/** Native LoRA-page filter state, without global storage, routes or a second Loader mount.
 * Storage/reload effects are explicit plans for the selected manager-page caller.
 * No workflow/widget storage is silently substituted for manager restoration.
 */
const EMPTY_WILDCARD_MARKER = '__EMPTY_WILDCARD_RESULT__';
const LORA_AVAILABILITY_STATUSES = ['ready', 'missing', 'deleted'];
export function buildActiveFiltersPayload(pageType, getStorageItem) {
    const activeFolder = getStorageItem(`${pageType}_activeFolder`);
    const recursiveSearch = getStorageItem(`${pageType}_recursiveSearch`, true);
    const filters = getStorageItem(`${pageType}_filters`);

    return {
        // null stays null; legacy "null" string is normalized to null
        activeFolder: activeFolder && activeFolder !== 'null' ? activeFolder : null,
        recursiveSearch: recursiveSearch !== false,
        filters: filters && typeof filters === 'object' ? filters : null,
    };
}

export class LoraActiveFilterState {
    constructor({ pageState, activeFolder = null, recursiveSearch = true,
                  persistedFilters = null, activePreset = null }) {
        if (!pageState || typeof pageState !== 'object') throw new TypeError('Actual manager page state required');
        this.currentPage = 'loras';
        this.pageState = pageState;
        this.filters = this.initializeFilters(pageState.filters);
        this.activeFolder = activeFolder;
        this.recursiveSearch = recursiveSearch;
        this.persistedFilters = persistedFilters;
        this.activePreset = activePreset;
        this.listeners = new Set();
        this.disposed = false;
        this.loadFiltersFromStorage(persistedFilters);
        this.pageState.filters = this.cloneFilters();
    }
    assertLive() { if (this.disposed) throw new Error('Filter controller disposed'); }
    snapshot() { this.assertLive(); return this.cloneFilters(); }
    subscribe(listener) {
        this.assertLive();
        if (typeof listener !== 'function') throw new TypeError('Listener required');
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    }
    notify(plan) { for (const listener of [...this.listeners]) listener(plan); return plan; }
    mirrorPayload() {
        this.assertLive();
        const values = { loras_activeFolder: this.activeFolder,
            loras_recursiveSearch: this.recursiveSearch, loras_filters: this.persistedFilters };
        return buildActiveFiltersPayload('loras', (key, fallback = null) =>
            values[key] === undefined ? fallback : values[key]);
    }
    loadFiltersFromStorage(savedFilters) {
        this.assertLive();
        // Native restoration only normalizes a truthy saved snapshot.
        if (savedFilters) {
            this.filters = this.initializeFilters(savedFilters);
            this.pageState.filters = this.cloneFilters();
        }
    }
    selectBaseModel(value) {
        this.assertLive();
        if (this.filters.baseModel.includes(value)) {
            this.filters.baseModel = this.filters.baseModel.filter(m => m !== value);
        } else { this.filters.baseModel.push(value); }
        return this.applyFilters();
    }
    selectModelType(type) {
        this.assertLive();
        if (this.filters.modelTypes.includes(type)) {
            this.filters.modelTypes = this.filters.modelTypes.filter(value => value !== type);
        } else { this.filters.modelTypes.push(type); }
        return this.applyFilters();
    }
    cycle(group, key) {
        this.assertLive();
        if (!['tags', 'autoTags', 'license'].includes(group)) throw new TypeError('Native tri-state group required');
        if (!this.filters[group]) this.filters[group] = {};
        const next = this.getNextTriStateState(this.filters[group][key] || 'none');
        if (next === 'none') {
            delete this.filters[group][key];
            if (group === 'license' && Object.keys(this.filters.license).length === 0) delete this.filters.license;
        } else { this.filters[group][key] = next; }
        return this.applyFilters();
    }
    setTagLogic(value) {
        this.assertLive();
        if (this.filters.tagLogic === value) return null;
        this.filters.tagLogic = value;
        return this.applyFilters();
    }
    setTransientSearch(value) {
        this.assertLive();
        this.pageState.filters.search = value;
        return this.snapshot();
    }
    updateLocation(activeFolder, recursiveSearch) {
        this.assertLive();
        this.activeFolder = activeFolder;
        this.recursiveSearch = recursiveSearch;
        return this.notify({ storage: [
            { op: 'set', key: 'loras_activeFolder', value: activeFolder },
            { op: 'set', key: 'loras_recursiveSearch', value: recursiveSearch }],
            mirror: this.mirrorPayload() });
    }
    applyFilters({ isPresetApply = false } = {}) {
        this.assertLive();
        const filtersSnapshot = this.cloneFilters();
        filtersSnapshot.baseModel = filtersSnapshot.baseModel.filter(m => m !== EMPTY_WILDCARD_MARKER);
        delete filtersSnapshot.search;
        this.persistedFilters = filtersSnapshot;
        this.pageState.filters = this.cloneFilters();
        const clearPreset = !isPresetApply && Boolean(this.activePreset);
        if (clearPreset) this.activePreset = null;
        return this.notify({ storage: [{ op: 'set', key: 'loras_filters', value: filtersSnapshot }],
            clearPreset, reload: { reset: true, clear: false }, mirror: this.mirrorPayload(),
            active: this.hasActiveFilters() });
    }
    clearFilters() {
        this.assertLive();
        this.activePreset = null;
        this.filters = this.initializeFilters({ ...this.filters, baseModel: [], tags: {},
            autoTags: {}, license: {}, modelTypes: [], loraAvailability: [], tagLogic: 'any' });
        this.pageState.filters = this.cloneFilters();
        this.persistedFilters = null;
        return this.notify({ storage: [{ op: 'remove', key: 'loras_filters' }],
            clearPreset: true, abortTagSearch: true, tagSearchQuery: '',
            reloadTopTagsIfLoaded: true, reload: { reset: true, clear: true },
            mirror: this.mirrorPayload(), active: this.hasActiveFilters() });
    }
    dispose() {
        if (this.disposed) return;
        this.disposed = true;
        this.listeners.clear();
        // Neither browser persistence nor the shared mirror is cleared on dispose.
        // Native source retains both; only this owned observer lifetime ends.
    }
    initializeFilters(existingFilters = {}) {
        const source = existingFilters || {};
        return {
            ...source,
            baseModel: Array.isArray(source.baseModel) ? [...source.baseModel] : [],
            tags: this.normalizeTagFilters(source.tags),
            autoTags: this.normalizeTagFilters(source.autoTags),
            license: this.shouldShowLicenseFilters() ? this.normalizeLicenseFilters(source.license) : {},
            modelTypes: this.normalizeModelTypeFilters(source.modelTypes),
            loraAvailability: this.normalizeLoraAvailabilityFilters(source.loraAvailability),
            tagLogic: source.tagLogic || 'any'
        };
    }

    shouldShowLicenseFilters() {
        return this.currentPage !== 'recipes';
    }

    shouldShowLoraAvailabilityFilter() {
        return this.currentPage === 'recipes';
    }

    normalizeLoraAvailabilityFilters(loraAvailability) {
        // Default to no statuses selected (= no filtering)
        if (!Array.isArray(loraAvailability)) {
            return [];
        }

        const seen = new Set();
        return loraAvailability.reduce((acc, status) => {
            if (typeof status !== 'string') {
                return acc;
            }

            const normalized = status.trim().toLowerCase();
            if (!LORA_AVAILABILITY_STATUSES.includes(normalized) || seen.has(normalized)) {
                return acc;
            }

            seen.add(normalized);
            acc.push(normalized);
            return acc;
        }, []);
    }

    normalizeTagFilters(tagFilters) {
        if (!tagFilters) {
            return {};
        }

        if (Array.isArray(tagFilters)) {
            return tagFilters.reduce((acc, tag) => {
                if (typeof tag === 'string' && tag.trim().length > 0) {
                    acc[tag] = 'include';
                }
                return acc;
            }, {});
        }

        if (typeof tagFilters === 'object') {
            const normalized = {};
            Object.entries(tagFilters).forEach(([tag, state]) => {
                if (!tag) {
                    return;
                }
                const normalizedState = typeof state === 'string' ? state.toLowerCase() : '';
                if (normalizedState === 'include' || normalizedState === 'exclude') {
                    normalized[tag] = normalizedState;
                }
            });
            return normalized;
        }

        return {};
    }

    normalizeLicenseFilters(licenseFilters) {
        if (!licenseFilters || typeof licenseFilters !== 'object') {
            return {};
        }

        const normalized = {};
        Object.entries(licenseFilters).forEach(([key, state]) => {
            const normalizedState = typeof state === 'string' ? state.toLowerCase() : '';
            if (normalizedState === 'include' || normalizedState === 'exclude') {
                normalized[key] = normalizedState;
            }
        });
        return normalized;
    }

    normalizeModelTypeFilters(modelTypes) {
        if (!Array.isArray(modelTypes)) {
            return [];
        }

        const seen = new Set();
        return modelTypes.reduce((acc, type) => {
            if (typeof type !== 'string') {
                return acc;
            }

            const normalized = type.trim().toLowerCase();
            if (!normalized || seen.has(normalized)) {
                return acc;
            }

            seen.add(normalized);
            acc.push(normalized);
            return acc;
        }, []);
    }

    getNextTriStateState(currentState) {
        switch (currentState) {
            case 'none':
                return 'include';
            case 'include':
                return 'exclude';
            default:
                return 'none';
        }
    }

    setTagFilterState(tagName, state) {
        if (!this.filters.tags) {
            this.filters.tags = {};
        }

        if (state === 'none') {
            delete this.filters.tags[tagName];
        } else {
            this.filters.tags[tagName] = state;
        }
    }

    hasActiveFilters() {
        const tagCount = this.filters.tags ? Object.keys(this.filters.tags).length : 0;
        const autoTagCount = this.filters.autoTags ? Object.keys(this.filters.autoTags).length : 0;
        const licenseCount = this.filters.license ? Object.keys(this.filters.license).length : 0;
        const modelTypeCount = this.filters.modelTypes.length;
        // Exclude EMPTY_WILDCARD_MARKER from base model count
        const baseModelCount = this.filters.baseModel.filter(m => m !== EMPTY_WILDCARD_MARKER).length;
        const loraAvailabilityCount = this.filters.loraAvailability?.length ?? 0;
        return (
            baseModelCount > 0 ||
            tagCount > 0 ||
            autoTagCount > 0 ||
            licenseCount > 0 ||
            modelTypeCount > 0 ||
            loraAvailabilityCount > 0
        );
    }

    cloneFilters() {
        const pageState = this.pageState;
        return {
            ...this.filters,
            baseModel: [...(this.filters.baseModel || [])],
            tags: { ...(this.filters.tags || {}) },
            autoTags: { ...(this.filters.autoTags || {}) },
            license: { ...(this.filters.license || {}) },
            modelTypes: [...(this.filters.modelTypes || [])],
            loraAvailability: [...(this.filters.loraAvailability || [])],
            tagLogic: this.filters.tagLogic || 'any',
            search: pageState?.filters?.search ?? ''
        };
    }
}
