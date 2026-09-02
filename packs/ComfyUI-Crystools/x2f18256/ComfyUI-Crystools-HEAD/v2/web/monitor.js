import { comfy } from '/comfy/api/v2.js';
import { commonPrefix } from './common.js';
import { MonitorUI } from './monitorUI.js';
import { Colors } from './styles.js';
import { convertNumberToPascalCase } from './utils.js';
class CrystoolsMonitor {
    constructor() {
        Object.defineProperty(this, "idExtensionName", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: 'Crystools.monitor'
        });
        Object.defineProperty(this, "menuPrefix", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: commonPrefix
        });
        Object.defineProperty(this, "settingsRate", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: void 0
        });
        Object.defineProperty(this, "settingsMonitorHeight", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: void 0
        });
        Object.defineProperty(this, "settingsMonitorWidth", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: void 0
        });
        Object.defineProperty(this, "monitorCPUElement", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: void 0
        });
        Object.defineProperty(this, "monitorRAMElement", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: void 0
        });
        Object.defineProperty(this, "monitorHDDElement", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: void 0
        });
        Object.defineProperty(this, "settingsHDD", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: void 0
        });
        Object.defineProperty(this, "monitorGPUSettings", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: []
        });
        Object.defineProperty(this, "monitorVRAMSettings", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: []
        });
        Object.defineProperty(this, "monitorTemperatureSettings", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: []
        });
        Object.defineProperty(this, "monitorUI", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: void 0
        });
        Object.defineProperty(this, "monitorWidthId", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: 'Crystools.MonitorWidth'
        });
        Object.defineProperty(this, "monitorWidth", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: 60
        });
        Object.defineProperty(this, "monitorHeightId", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: 'Crystools.MonitorHeight'
        });
        Object.defineProperty(this, "monitorHeight", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: 30
        });
        Object.defineProperty(this, "createSettingsRate", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: () => {
                this.settingsRate = {
                    id: 'Crystools.RefreshRate',
                    name: 'Refresh per second',
                    category: ['Crystools', this.menuPrefix + ' Configuration', 'refresh'],
                    tooltip: 'This is the time (in seconds) between each update of the monitors, 0 means no refresh',
                    type: 'slider',
                    attrs: {
                        min: 0,
                        max: 2,
                        step: .25,
                    },
                    defaultValue: .5,
                    onChange: async (value) => {
                        let valueNumber;
                        try {
                            valueNumber = parseFloat(value);
                            if (isNaN(valueNumber)) {
                                throw new Error('invalid value');
                            }
                        }
                        catch (error) {
                            console.error(error);
                            return;
                        }
                        this.refreshSeconds = valueNumber;
                        this.restartPolling();
                        const data = {
                            cpu_utilization: 0,
                            device: 'cpu',
                            gpus: [
                                {
                                    gpu_utilization: 0,
                                    gpu_temperature: 0,
                                    vram_total: 0,
                                    vram_used: 0,
                                    vram_used_percent: 0,
                                },
                            ],
                            hdd_total: 0,
                            hdd_used: 0,
                            hdd_used_percent: 0,
                            ram_total: 0,
                            ram_used: 0,
                            ram_used_percent: 0,
                        };
                        if (valueNumber === 0) {
                            this.monitorUI.updateDisplay(data);
                        }
                    },
                };
            }
        });
        Object.defineProperty(this, "createSettingsMonitorWidth", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: () => {
                this.settingsMonitorWidth = {
                    id: this.monitorWidthId,
                    name: 'Pixel Width',
                    category: ['Crystools', this.menuPrefix + ' Configuration', 'width'],
                    tooltip: 'The width of the monitor in pixels on the UI (only on top/bottom UI)',
                    type: 'slider',
                    attrs: {
                        min: 60,
                        max: 100,
                        step: 1,
                    },
                    defaultValue: this.monitorWidth,
                    // COSMETIC: top-bar badges follow the host's width. This setting
                    // remains declared so an existing stored value is not discarded.
                    onChange: () => { },
                };
            }
        });
        Object.defineProperty(this, "createSettingsMonitorHeight", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: () => {
                this.settingsMonitorHeight = {
                    id: this.monitorHeightId,
                    name: 'Pixel Height',
                    category: ['Crystools', this.menuPrefix + ' Configuration', 'height'],
                    tooltip: 'The height of the monitor in pixels on the UI (only on top/bottom UI)',
                    type: 'slider',
                    attrs: {
                        min: 16,
                        max: 50,
                        step: 1,
                    },
                    defaultValue: this.monitorHeight,
                    // See Pixel Width above: inert, and kept only to hold the value.
                    onChange: () => { },
                };
            }
        });
        Object.defineProperty(this, "createSettingsCPU", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: () => {
                this.monitorCPUElement = {
                    id: 'Crystools.ShowCpu',
                    name: 'CPU Usage',
                    category: ['Crystools', this.menuPrefix + ' Hardware', 'Cpu'],
                    type: 'boolean',
                    label: 'CPU',
                    symbol: '%',
                    defaultValue: true,
                    htmlMonitorRef: undefined,
                    htmlMonitorSliderRef: undefined,
                    htmlMonitorLabelRef: undefined,
                    cssColor: Colors.CPU,
                    onChange: async (value) => {
                        this.updateWidget(this.monitorCPUElement);
                    },
                };
            }
        });
        Object.defineProperty(this, "createSettingsRAM", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: () => {
                this.monitorRAMElement = {
                    id: 'Crystools.ShowRam',
                    name: 'RAM Used',
                    category: ['Crystools', this.menuPrefix + ' Hardware', 'Ram'],
                    type: 'boolean',
                    label: 'RAM',
                    symbol: '%',
                    defaultValue: true,
                    htmlMonitorRef: undefined,
                    htmlMonitorSliderRef: undefined,
                    htmlMonitorLabelRef: undefined,
                    cssColor: Colors.RAM,
                    onChange: async (value) => {
                        this.updateWidget(this.monitorRAMElement);
                    },
                };
            }
        });
        Object.defineProperty(this, "createSettingsGPUUsage", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: (name, index, moreThanOneGPU) => {
                if (name === undefined || index === undefined) {
                    console.warn('getGPUsFromServer: name or index undefined', name, index);
                    return;
                }
                let label = 'GPU ';
                label += moreThanOneGPU ? index : '';
                const monitorGPUNElement = {
                    id: 'Crystools.ShowGpuUsage' + convertNumberToPascalCase(index),
                    name: ' Usage',
                    category: ['Crystools', `${this.menuPrefix} Show GPU [${index}] ${name}`, 'Usage'],
                    type: 'boolean',
                    label,
                    symbol: '%',
                    monitorTitle: `${index}: ${name}`,
                    defaultValue: true,
                    htmlMonitorRef: undefined,
                    htmlMonitorSliderRef: undefined,
                    htmlMonitorLabelRef: undefined,
                    cssColor: Colors.GPU,
                    onChange: async (value) => {
                        this.updateWidget(monitorGPUNElement);
                    },
                };
                this.monitorGPUSettings[index] = monitorGPUNElement;
                comfy.settings.declare(this.monitorGPUSettings[index]);
            }
        });
        Object.defineProperty(this, "createSettingsGPUVRAM", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: (name, index, moreThanOneGPU) => {
                if (name === undefined || index === undefined) {
                    console.warn('getGPUsFromServer: name or index undefined', name, index);
                    return;
                }
                let label = 'VRAM ';
                label += moreThanOneGPU ? index : '';
                const monitorVRAMNElement = {
                    id: 'Crystools.ShowGpuVram' + convertNumberToPascalCase(index),
                    name: 'VRAM',
                    category: ['Crystools', `${this.menuPrefix} Show GPU [${index}] ${name}`, 'VRAM'],
                    type: 'boolean',
                    label: label,
                    symbol: '%',
                    monitorTitle: `${index}: ${name}`,
                    defaultValue: true,
                    htmlMonitorRef: undefined,
                    htmlMonitorSliderRef: undefined,
                    htmlMonitorLabelRef: undefined,
                    cssColor: Colors.VRAM,
                    onChange: async (value) => {
                        this.updateWidget(monitorVRAMNElement);
                    },
                };
                this.monitorVRAMSettings[index] = monitorVRAMNElement;
                comfy.settings.declare(this.monitorVRAMSettings[index]);
            }
        });
        Object.defineProperty(this, "createSettingsGPUTemp", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: (name, index, moreThanOneGPU) => {
                if (name === undefined || index === undefined) {
                    console.warn('getGPUsFromServer: name or index undefined', name, index);
                    return;
                }
                let label = 'Temp ';
                label += moreThanOneGPU ? index : '';
                const monitorTemperatureNElement = {
                    id: 'Crystools.ShowGpuTemperature' + convertNumberToPascalCase(index),
                    name: 'Temperature',
                    category: ['Crystools', `${this.menuPrefix} Show GPU [${index}] ${name}`, 'Temperature'],
                    type: 'boolean',
                    label: label,
                    symbol: '°',
                    monitorTitle: `${index}: ${name}`,
                    defaultValue: true,
                    htmlMonitorRef: undefined,
                    htmlMonitorSliderRef: undefined,
                    htmlMonitorLabelRef: undefined,
                    cssColor: Colors.TEMP_START,
                    cssColorFinal: Colors.TEMP_END,
                    onChange: async (value) => {
                        this.updateWidget(monitorTemperatureNElement);
                    },
                };
                this.monitorTemperatureSettings[index] = monitorTemperatureNElement;
                comfy.settings.declare(this.monitorTemperatureSettings[index]);
            }
        });
        Object.defineProperty(this, "createSettingsHDD", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: () => {
                this.monitorHDDElement = {
                    id: 'Crystools.ShowHdd',
                    name: 'Show HDD Used',
                    category: ['Crystools', this.menuPrefix + ' Show Hard Disk', 'Show'],
                    type: 'boolean',
                    label: 'HDD',
                    symbol: '%',
                    defaultValue: false,
                    htmlMonitorRef: undefined,
                    htmlMonitorSliderRef: undefined,
                    htmlMonitorLabelRef: undefined,
                    cssColor: Colors.DISK,
                    onChange: async (value) => {
                        this.updateWidget(this.monitorHDDElement);
                    },
                };
                this.settingsHDD = {
                    id: 'Crystools.WhichHdd',
                    name: 'Partition to show',
                    category: ['Crystools', this.menuPrefix + ' Show Hard Disk', 'Which'],
                    type: 'combo',
                    defaultValue: '/',
                    options: [],
                    onChange: async (value) => {
                        void value;
                    },
                };
            }
        });
        Object.defineProperty(this, "createSettings", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: () => {
                comfy.settings.declare(this.settingsRate);
                comfy.settings.declare(this.settingsMonitorHeight);
                comfy.settings.declare(this.settingsMonitorWidth);
                comfy.settings.declare(this.monitorRAMElement);
                void this.getGPUsFromServer().then((gpus) => {
                    let moreThanOneGPU = false;
                    if (gpus.length > 1) {
                        moreThanOneGPU = true;
                    }
                    gpus?.forEach(({ name, index }) => {
                        this.createSettingsGPUVRAM(name, index, moreThanOneGPU);
                    });
                    this.finishedLoad();
                });
            }
        });
        Object.defineProperty(this, "finishedLoad", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: () => {
                this.updateAllWidget();
            }
        });
        // Badges appear in the order they are registered, which is what the old
        // orderMonitors() achieved with a CSS `order`: CPU, RAM, then each GPU's
        // usage/VRAM/temperature, then HDD.
        Object.defineProperty(this, "updateAllWidget", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: () => {
                this.updateWidget(this.monitorCPUElement);
                this.updateWidget(this.monitorRAMElement);
                this.monitorGPUSettings.forEach((monitorSettings, index) => {
                    monitorSettings && this.updateWidget(monitorSettings);
                    this.monitorVRAMSettings[index] && this.updateWidget(this.monitorVRAMSettings[index]);
                    this.monitorTemperatureSettings[index] && this.updateWidget(this.monitorTemperatureSettings[index]);
                });
                this.updateWidget(this.monitorHDDElement);
            }
        });
        Object.defineProperty(this, "updateWidget", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: (monitorSettings) => {
                if (this.monitorUI) {
                    const value = comfy.settings.get(monitorSettings.id);
                    this.monitorUI.showMonitor(monitorSettings, value);
                }
            }
        });
        Object.defineProperty(this, "updateServer", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: async () => undefined
        });
        Object.defineProperty(this, "updateServerGPU", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: async () => undefined
        });
        Object.defineProperty(this, "getHDDsFromServer", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: async () => {
                return [];
            }
        });
        Object.defineProperty(this, "getGPUsFromServer", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: async () => {
                const data = await this.getDataFromServer();
                return (data.devices || [])
                    .filter((device) => device.type !== 'cpu')
                    .map((device, index) => ({ name: device.name, index }));
            }
        });
        Object.defineProperty(this, "getDataFromServer", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: async () => {
                const resp = await comfy.backend.fetch('/system_stats', {
                    method: 'GET',
                    cache: 'no-store',
                });
                if (resp.status === 200) {
                    return await resp.json();
                }
                throw new Error(resp.statusText);
            }
        });
        Object.defineProperty(this, "poll", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: async () => {
                try {
                    const data = await this.getDataFromServer();
                    const system = data.system || {};
                    const ramTotal = Number(system.ram_total || 0);
                    const ramFree = Number(system.ram_free || 0);
                    const percent = (total, free) => total > 0
                        ? Math.max(0, Math.min(100, (total - free) * 100 / total))
                        : -1;
                    const gpus = (data.devices || [])
                        .filter((device) => device.type !== 'cpu')
                        .map((device) => {
                            const total = Number(device.vram_total || 0);
                            const free = Number(device.vram_free || 0);
                            return {
                                gpu_utilization: -1,
                                gpu_temperature: -1,
                                vram_total: total,
                                vram_used: Math.max(0, total - free),
                                vram_used_percent: percent(total, free),
                            };
                        });
                    this.monitorUI?.updateDisplay({
                        cpu_utilization: -1,
                        device: 'host',
                        gpus,
                        hdd_total: 0,
                        hdd_used: 0,
                        hdd_used_percent: -1,
                        ram_total: ramTotal,
                        ram_used: Math.max(0, ramTotal - ramFree),
                        ram_used_percent: percent(ramTotal, ramFree),
                    });
                }
                catch (error) {
                    console.warn('Crystools system statistics are unavailable', error);
                }
            }
        });
        Object.defineProperty(this, "restartPolling", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: () => {
                if (this.pollTimer !== undefined) {
                    clearInterval(this.pollTimer);
                    this.pollTimer = undefined;
                }
                const seconds = Number(this.refreshSeconds ?? .5);
                if (seconds <= 0) {
                    return;
                }
                void this.poll();
                this.pollTimer = setInterval(
                    () => void this.poll(), Math.max(250, seconds * 1000));
            }
        });
        Object.defineProperty(this, "setup", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: () => {
                if (this.monitorUI) {
                    return;
                }
                this.createSettingsRate();
                this.createSettingsMonitorHeight();
                this.createSettingsMonitorWidth();
                this.createSettingsCPU();
                this.createSettingsRAM();
                this.createSettingsHDD();
                this.createSettings();
                // Which side of the menu bar the monitors sit on was the pack's to
                // choose while it inserted its own element; the host places its own
                // chrome now, so Comfy.UseNewMenu is no longer ours to follow.
                this.monitorUI = new MonitorUI(this.monitorCPUElement, this.monitorRAMElement, this.monitorHDDElement, this.monitorGPUSettings, this.monitorVRAMSettings, this.monitorTemperatureSettings);
                this.registerListeners();
            }
        });
        Object.defineProperty(this, "registerListeners", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: () => {
                this.refreshSeconds = Number(
                    comfy.settings.get(this.settingsRate.id) ?? .5);
                this.restartPolling();
            }
        });
    }
}
const crystoolsMonitor = new CrystoolsMonitor();
comfy.onReady(crystoolsMonitor.setup);
