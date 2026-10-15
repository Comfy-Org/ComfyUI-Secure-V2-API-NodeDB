// Literal native query/match/preference methods; local names are strings only.
// Keyboard intent and insertion plans are pure and are NOT wired to a fake
// cancellable textarea event or an invented syntax/usage-tip producer.
function normalizeAutocompleteMatchText(text = '') {
    return text.toLowerCase().replace(/[-_\s']/g, '');
}

function removeLoraExtension(fileName = '') {
    return fileName.replace(/\.(safetensors|ckpt|pt|bin)$/i, '');
}

export class LoaderAutocompleteSelection {
    constructor() {
        this.options = { minChars: 1 };
        this.items = []; this.selectedIndex = -1; this.hasManualSelection = false;
        this.showingCommands = false; this.lastAccepted = null;
    }
    _getDisplayText(item) {
        // Selected source branch: this.modelType === 'loras', plain catalogue names.
        return removeLoraExtension(item);
    }
    reset() {
        this.items = []; this.selectedIndex = -1; this.hasManualSelection = false;
    }
    replace(items, term) {
        this.reset(); this.items = items.slice();
        this.selectedIndex = this._getPreferredSelectedIndex(term);
    }
    select(index, manual = false) {
        if (index >= 0 && index < this.items.length) {
            this.selectedIndex = index; this.hasManualSelection = manual;
        }
    }
    keyIntent(key, liveTerm, mode = 'both') {
        if (!this.items.length) return { kind: 'pass' };
        if (key === 'ArrowDown' || key === 'ArrowUp') {
            const next = key === 'ArrowDown'
                ? Math.min(this.selectedIndex + 1, this.items.length - 1)
                : Math.max(this.selectedIndex - 1, 0);
            this.select(next, true);
            return { kind: 'select', index: this.selectedIndex, requiresKeyClaim: true };
        }
        if (key === 'Escape') return { kind: 'hide', requiresKeyClaim: true };
        const accepted = mode === 'tab_only' ? key === 'Tab'
            : mode === 'enter_only' ? key === 'Enter' : key === 'Tab' || key === 'Enter';
        if (!accepted) return { kind: 'pass' };
        const index = this._getAcceptSelectionIndex(liveTerm);
        if (index < 0) return { kind: 'pass' };
        this.select(index, this.hasManualSelection);
        return { kind: 'accept', item: this.items[index], index, requiresKeyClaim: true,
                 requiresNativeInsertionProducer: true };
    }
    range(currentValue, caretPos, appendComma) {
        if (typeof currentValue !== 'string' || !Number.isInteger(caretPos) ||
            caretPos < 0 || caretPos > currentValue.length) throw new Error('Invalid live text/caret');
        const beforeCursor = currentValue.substring(0, caretPos);
        let start = this._getHardBoundaryStart(beforeCursor);
        if (!appendComma && this.lastAccepted) {
            const { start: oldStart, end, insertedText, textSnapshot } = this.lastAccepted;
            if (!Number.isInteger(oldStart) || !Number.isInteger(end) || oldStart < 0 || end < oldStart ||
                end > currentValue.length || end > caretPos || typeof insertedText !== 'string' ||
                !insertedText || currentValue.slice(oldStart, end) !== insertedText ||
                typeof textSnapshot !== 'string' || currentValue.slice(0, end) !== textSnapshot) {
                this.lastAccepted = null;
            } else if (end > start) start = end;
        }
        const rawText = beforeCursor.substring(start);
        const leadingWhitespaceLength = rawText.length - rawText.trimStart().length;
        return { start, trimmedStart: start + leadingWhitespaceLength, end: caretPos,
                 beforeCursor, rawText, text: rawText.trim() };
    }
    resolvedInsertion(currentValue, caret, insertText, appendComma) {
        // The caller must obtain genuine native insertion text FIRST and then
        // read the current input/caret, as the pinned async insertion does.
        if (typeof insertText !== 'string') throw new Error('Unselected native insertion text');
        if (!insertText) return null;
        const activeRange = this.range(currentValue, caret, appendComma);
        const start = activeRange.trimmedStart;
        const value = currentValue.substring(0, start) + insertText + currentValue.substring(caret);
        const end = start + insertText.length;
        this.lastAccepted = { start, end, insertedText: insertText, textSnapshot: value.substring(0, end) };
        return { value, caret: end };
    }
    restore() { this.reset(); this.lastAccepted = null; }
    _getHardBoundaryStart(beforeCursor = '') {
        const lastComma = beforeCursor.lastIndexOf(',');
        const lastAngle = beforeCursor.lastIndexOf('>');
        const lastNewline = Math.max(beforeCursor.lastIndexOf('\n'), beforeCursor.lastIndexOf('\r'));
        return Math.max(lastComma, lastAngle, lastNewline) + 1;
    }

    _getLastSpaceToken(term) {
        const tokens = term.trim().split(/\s+/);
        return tokens[tokens.length - 1] || term;
    }

    _generateQueryVariations(term) {
        if (!term || term.length < this.options.minChars) {
            return [];
        }

        const variations = new Set();
        const trimmed = term.trim();

        // Always include original query
        variations.add(trimmed);
        variations.add(trimmed.toLowerCase());

        // Add underscore version (Danbooru convention: spaces become underscores)
        // e.g., "looking to the side" -> "looking_to_the_side"
        if (trimmed.includes(' ')) {
            const underscoreVersion = trimmed.replace(/ /g, '_');
            variations.add(underscoreVersion);
            variations.add(underscoreVersion.toLowerCase());
        }

        // Add no-space version for flexible matching
        // e.g., "blue hair" -> "bluehair"
        if (trimmed.includes(' ') || trimmed.includes('_')) {
            const noSpaceVersion = trimmed.replace(/[ _]/g, '');
            variations.add(noSpaceVersion);
            variations.add(noSpaceVersion.toLowerCase());
        }

        // Add last token only (legacy behavior for continuous typing)
        const lastToken = this._getLastSpaceToken(trimmed);
        if (lastToken !== trimmed) {
            variations.add(lastToken);
            variations.add(lastToken.toLowerCase());
        }

        return Array.from(variations).filter(v => v.length >= this.options.minChars);
    }

    _normalizeQueryForRequest(term = '') {
        return term.trim().toLowerCase();
    }

    _getQueriesToExecute(term = '') {
        const queryVariations = this._generateQueryVariations(term);
        const uniqueQueries = [];
        const seen = new Set();

        for (const query of queryVariations) {
            const normalized = this._normalizeQueryForRequest(query);
            if (!normalized || seen.has(normalized)) {
                continue;
            }

            seen.add(normalized);
            uniqueQueries.push(query);

            if (uniqueQueries.length >= 4) {
                break;
            }
        }

        return uniqueQueries;
    }

    _matchItem(item, searchTerm) {
        const itemText = this._getDisplayText(item);
        const itemTextLower = itemText.toLowerCase();
        const searchTermLower = searchTerm.toLowerCase();

        // Exact match (case-insensitive)
        if (itemTextLower === searchTermLower) {
            return { matched: true, isExactMatch: true };
        }

        // Partial match (contains)
        if (itemTextLower.includes(searchTermLower)) {
            return { matched: true, isExactMatch: false };
        }

        // Symbol-insensitive match: remove common separators and retry
        // e.g., "blue hair" can match "blue_hair" or "bluehair"
        const normalizedItem = itemTextLower.replace(/[-_\s']/g, '');
        const normalizedSearch = searchTermLower.replace(/[-_\s']/g, '');
        if (normalizedItem.includes(normalizedSearch)) {
            return { matched: true, isExactMatch: false };
        }

        return { matched: false, isExactMatch: false };
    }

    _getPreferredSelectedIndex(searchTerm = '') {
        if (!this.items?.length) {
            return -1;
        }

        if (this.showingCommands) {
            if (this.selectedIndex >= 0 && this.selectedIndex < this.items.length) {
                return this.selectedIndex;
            }
            return 0;
        }

        const trimmedSearchTerm = searchTerm.trim();
        if (!trimmedSearchTerm) {
            if (this.selectedIndex >= 0 && this.selectedIndex < this.items.length) {
                return this.selectedIndex;
            }
            return 0;
        }

        const searchLower = trimmedSearchTerm.toLowerCase();
        const normalizedSearch = normalizeAutocompleteMatchText(trimmedSearchTerm);
        let bestIndex = -1;
        let bestScore = -Infinity;

        this.items.forEach((item, index) => {
            const displayText = this._getDisplayText(item);
            const textLower = displayText.toLowerCase();
            const normalizedText = normalizeAutocompleteMatchText(displayText);
            let score = -1;

            if (textLower === searchLower) {
                score = 5000;
            } else if (normalizedText === normalizedSearch) {
                score = 4500;
            } else if (textLower.startsWith(searchLower)) {
                score = 4000;
            } else if (normalizedText.startsWith(normalizedSearch)) {
                score = 3500;
            } else if (textLower.includes(searchLower)) {
                score = 3000;
            } else if (normalizedText.includes(normalizedSearch)) {
                score = 2500;
            }

            if (score > -1) {
                score -= index;
                if (score > bestScore) {
                    bestScore = score;
                    bestIndex = index;
                }
            }
        });

        if (bestIndex !== -1) {
            return bestIndex;
        }

        if (this.selectedIndex >= 0 && this.selectedIndex < this.items.length) {
            return this.selectedIndex;
        }

        return 0;
    }

    _getAcceptSelectionIndex(searchTerm = '') {
        if (this.hasManualSelection && this.selectedIndex >= 0 && this.selectedIndex < this.items.length) {
            return this.selectedIndex;
        }

        return this._getPreferredSelectedIndex(searchTerm);
    }
}
