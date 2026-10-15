/** Original GalleryWidget selection behavior over a public widget handle. */
export class GallerySelectionController {
    constructor(widget, options, delegate, repaint = () => {}, nativeValue = null) {
        this.widget = widget;
        this.nativeValue = nativeValue;
        this.options = {height:48,allow_variants:false,...options};
        this._selectedIndex = -1;
        this.itemArray = [];
        this.repaint = repaint;
        this.disposed = false;
        this.ready = delegate.fetchItemArray().then(itemArray => {
            if (this.disposed) return;
            if (Array.isArray(itemArray) && itemArray.length > 0) {
                this.itemArray = itemArray;
                if (this.value == null) this.value = itemArray[0]?.name || '';
                this._selectedIndex = null;
                this.forceUpdate();
            }
        });
    }
    get value() {return this.nativeValue ? this.nativeValue.current : this.widget.getValue();}
    set value(value) {if (this.nativeValue) this.nativeValue.current = value;this.widget.setValue(value);}
    get selectedIndex() {
        if (this._selectedIndex == null) {
            this._selectedIndex = -1;
            if (this.value && Array.isArray(this.itemArray)) {
                this._selectedIndex = this.itemArray.findIndex(item => item.name === this.value);
            }
        }
        return this._selectedIndex;
    }
    set selectedIndex(index) {
        if (!Array.isArray(this.itemArray) || this.itemArray.length === 0) return;
        index = Math.max(0, Math.min(index, this.itemArray.length - 1));
        if (index == this._selectedIndex) return;
        this.forceUpdate(this.itemArray[index].name);
        this._selectedIndex = index;
    }
    forceUpdate(newValue) {
        const oldValue = this.value;
        this.value = newValue || this.value;
        if (this.value !== oldValue) this._selectedIndex = null;
        this.repaint();
    }
    computeSize(widgetWidth) {return [widgetWidth || 0,this.options.height];}
    dispose() {this.disposed = true;this.repaint = () => {};}
}
