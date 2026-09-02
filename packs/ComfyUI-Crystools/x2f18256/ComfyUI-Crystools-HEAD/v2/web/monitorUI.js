import { comfy } from '/comfy/api/v2.js';
import { formatBytes } from './utils.js';
export class MonitorUI {
    constructor(monitorCPUElement, monitorRAMElement, monitorHDDElement, monitorGPUSettings, monitorVRAMSettings, monitorTemperatureSettings) {
        Object.defineProperty(this, "monitorCPUElement", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: monitorCPUElement
        });
        Object.defineProperty(this, "monitorRAMElement", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: monitorRAMElement
        });
        Object.defineProperty(this, "monitorHDDElement", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: monitorHDDElement
        });
        Object.defineProperty(this, "monitorGPUSettings", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: monitorGPUSettings
        });
        Object.defineProperty(this, "monitorVRAMSettings", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: monitorVRAMSettings
        });
        Object.defineProperty(this, "monitorTemperatureSettings", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: monitorTemperatureSettings
        });
        Object.defineProperty(this, "badges", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: new Map()
        });
        Object.defineProperty(this, "readouts", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: new Map()
        });
        Object.defineProperty(this, "maxVRAMUsed", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: {}
        });
        Object.defineProperty(this, "updateDisplay", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: (data) => {
                this.updateMonitor(this.monitorCPUElement, data.cpu_utilization);
                this.updateMonitor(this.monitorRAMElement, data.ram_used_percent, data.ram_used, data.ram_total);
                this.updateMonitor(this.monitorHDDElement, data.hdd_used_percent, data.hdd_used, data.hdd_total);
                if (data.gpus === undefined || data.gpus.length === 0) {
                    return;
                }
                this.monitorGPUSettings.forEach((monitorSettings, index) => {
                    if (data.gpus[index]) {
                        const gpu = data.gpus[index];
                        if (gpu === undefined) {
                            return;
                        }
                        this.updateMonitor(monitorSettings, gpu.gpu_utilization);
                    }
                    else {
                    }
                });
                this.monitorVRAMSettings.forEach((monitorSettings, index) => {
                    if (data.gpus[index]) {
                        const gpu = data.gpus[index];
                        if (gpu === undefined) {
                            return;
                        }
                        this.updateMonitor(monitorSettings, gpu.vram_used_percent, gpu.vram_used, gpu.vram_total);
                    }
                    else {
                    }
                });
                this.monitorTemperatureSettings.forEach((monitorSettings, index) => {
                    if (data.gpus[index]) {
                        const gpu = data.gpus[index];
                        if (gpu === undefined) {
                            return;
                        }
                        this.updateMonitor(monitorSettings, gpu.gpu_temperature);
                    }
                    else {
                    }
                });
            }
        });
        Object.defineProperty(this, "updateMonitor", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: (monitorSettings, percent, used, total) => {
                if (!monitorSettings) {
                    return;
                }
                if (percent < 0) {
                    return;
                }
                const prefix = monitorSettings.monitorTitle ? monitorSettings.monitorTitle + ' - ' : '';
                let title = `${Math.floor(percent)}${monitorSettings.symbol}`;
                let postfix = '';
                if (used !== undefined && total !== undefined) {
                    const gpuIndex = parseInt(monitorSettings.monitorTitle?.split(':')[0] || '0');
                    if (!this.maxVRAMUsed[gpuIndex] || this.maxVRAMUsed[gpuIndex] > total) {
                        this.maxVRAMUsed[gpuIndex] = 0;
                    }
                    if (used > this.maxVRAMUsed[gpuIndex]) {
                        this.maxVRAMUsed[gpuIndex] = used;
                    }
                    postfix = ` - ${formatBytes(used)} / ${formatBytes(total)}`;
                    postfix += ` Max: ${formatBytes(this.maxVRAMUsed[gpuIndex])}`;
                }
                title = `${prefix}${title}${postfix}`;
                const readout = {
                    text: `${Math.floor(percent)}${monitorSettings.symbol}`,
                    tooltip: title,
                };
                this.readouts.set(monitorSettings.id, readout);
                this.badges.get(monitorSettings.id)?.update(readout);
            }
        });
        // The per-monitor bar colour (Colors.CPU/RAM/…, and the temperature ramp
        // between TEMP_START and TEMP_END) has no equivalent: a badge carries a
        // `variant` of info/warning/error and nothing finer. Badge order is
        // registration order, so a readout switched back on returns at the end
        // rather than in its original place.
        Object.defineProperty(this, "showMonitor", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: (monitorSettings, value) => {
                if (!monitorSettings) {
                    return;
                }
                const existing = this.badges.get(monitorSettings.id);
                if (!value) {
                    if (existing) {
                        existing.remove();
                        this.badges.delete(monitorSettings.id);
                    }
                    return;
                }
                if (existing) {
                    return;
                }
                const readout = this.readouts.get(monitorSettings.id);
                this.badges.set(monitorSettings.id, comfy.ui.addTopBarBadge({
                    id: monitorSettings.id,
                    label: monitorSettings.label,
                    text: readout ? readout.text : `0${monitorSettings.symbol}`,
                    tooltip: readout ? readout.tooltip : monitorSettings.monitorTitle,
                }));
            }
        });
        Object.defineProperty(this, "resetMaxVRAM", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: () => {
                this.maxVRAMUsed = {};
            }
        });
    }
}
