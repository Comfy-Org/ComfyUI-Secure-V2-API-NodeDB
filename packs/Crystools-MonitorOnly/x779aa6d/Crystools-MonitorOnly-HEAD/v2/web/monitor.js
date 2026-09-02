import { comfy } from '/comfy/api/v2.js'

export const SECURE_EXTENSION_ID = 'CrysMonitor.monitor'

const settings = {
  rate: 'CrysMonitor.RefreshRate',
  width: 'CrysMonitor.MonitorWidth',
  height: 'CrysMonitor.MonitorHeight',
  legacyHeight: 'CrysMonitor.MonitorHeightLegacy',
  disableSmooth: 'CrysMonitor.DisableSmooth',
  numbersOnly: 'CrysMonitor.NumbersOnly',
  cpu: 'CrysMonitor.ShowCpu',
  ram: 'CrysMonitor.ShowRam',
  hdd: 'CrysMonitor.ShowHdd',
  volume: 'CrysMonitor.WhichHdd',
}

const state = {
  badges: new Map(),
  maxMemory: new Map(),
  snapshot: undefined,
  timer: undefined,
  polling: false,
  ready: false,
}

function percent(total, available) {
  return total > 0
    ? Math.max(0, Math.min(100, ((total - available) * 100) / total))
    : null
}

function bytes(value) {
  if (!Number.isFinite(value) || value < 1) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  const unit = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1)
  const amount = value / (1024 ** unit)
  return `${amount.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`
}

function reading(value, symbol) {
  return value === null || value === undefined
    ? `--${symbol}`
    : `${Math.floor(value)}${symbol}`
}

function setBadge(id, visible, def) {
  const existing = state.badges.get(id)
  if (!visible) {
    existing?.remove()
    state.badges.delete(id)
    return
  }
  if (existing) existing.update(def)
  else state.badges.set(id, comfy.ui.addTopBarBadge({ id, ...def }))
}

function selectedVolume(snapshot) {
  if (!snapshot?.volumes.length) return undefined
  const selected = comfy.settings.get(settings.volume)
  return snapshot.volumes.find(({ id }) => id === selected) ?? snapshot.volumes[0]
}

function updateBadges(snapshot = state.snapshot) {
  if (!snapshot) return
  const cpu = snapshot.cpu.utilization_percent
  setBadge(settings.cpu, comfy.settings.get(settings.cpu) !== false, {
    label: 'CPU', text: reading(cpu, '%'), tooltip: `CPU - ${reading(cpu, '%')}`,
  })

  const ram = percent(snapshot.memory.total, snapshot.memory.available)
  const ramUsed = snapshot.memory.total - snapshot.memory.available
  setBadge(settings.ram, comfy.settings.get(settings.ram) !== false, {
    label: 'RAM', text: reading(ram, '%'),
    tooltip: `RAM - ${reading(ram, '%')} - ${bytes(ramUsed)} / ${bytes(snapshot.memory.total)}`,
  })

  const volume = selectedVolume(snapshot)
  const disk = volume ? percent(volume.total, volume.available) : null
  const diskUsed = volume ? volume.total - volume.available : 0
  setBadge(settings.hdd, comfy.settings.get(settings.hdd) === true, {
    label: 'HDD', text: reading(disk, '%'),
    tooltip: volume
      ? `${volume.label} - ${reading(disk, '%')} - ${bytes(diskUsed)} / ${bytes(volume.total)}`
      : 'No monitored volume is available',
  })

  snapshot.accelerators.forEach((accelerator, index) => {
    const suffix = snapshot.accelerators.length === 1 ? '' : String(index)
    const usageId = `CrysMonitor.ShowGpuUsage${index}`
    const vramId = `CrysMonitor.ShowGpuVram${index}`
    const temperatureId = `CrysMonitor.ShowGpuTemperature${index}`
    const used = accelerator.memory_total - accelerator.memory_available
    const vram = percent(accelerator.memory_total, accelerator.memory_available)
    state.maxMemory.set(
      accelerator.id,
      Math.max(state.maxMemory.get(accelerator.id) ?? 0, used),
    )
    setBadge(usageId, comfy.settings.get(usageId) !== false, {
      label: `GPU${suffix}`,
      text: reading(accelerator.utilization_percent, '%'),
      tooltip: `${accelerator.name} - ${reading(accelerator.utilization_percent, '%')}`,
    })
    setBadge(vramId, comfy.settings.get(vramId) !== false, {
      label: `VRAM${suffix}`,
      text: reading(vram, '%'),
      tooltip: `${accelerator.name} - ${reading(vram, '%')} - ${bytes(used)} / ${bytes(accelerator.memory_total)} Max: ${bytes(state.maxMemory.get(accelerator.id))}`,
    })
    setBadge(temperatureId, comfy.settings.get(temperatureId) !== false, {
      label: `Temp${suffix}`,
      text: reading(accelerator.temperature_c, '°'),
      tooltip: `${accelerator.name} - ${reading(accelerator.temperature_c, '°')}`,
    })
  })
}

function declareBaseSettings() {
  const category = (section, name) => ['CrysMonitor', section, name]
  comfy.settings.declare({
    id: settings.rate, name: 'Refresh per second', type: 'slider',
    defaultValue: 1, attrs: { min: 0, max: 2, step: 0.25 },
    category: category('Configuration', 'refresh'),
    tooltip: 'This is the time (in seconds) between each update of the monitors, 0 means no refresh',
    onChange: restartPolling,
  })
  comfy.settings.declare({
    id: settings.width, name: 'Pixel Width', type: 'slider', defaultValue: 60,
    attrs: { min: 60, max: 100, step: 1 }, category: category('Configuration', 'width'),
    tooltip: 'The width of the monitor in pixels on the UI (only on top/bottom UI)',
  })
  comfy.settings.declare({
    id: settings.height, name: 'Pixel Height (New Menu)', type: 'slider', defaultValue: 40,
    attrs: { min: 16, max: 50, step: 1 }, category: category('Configuration', 'height'),
    tooltip: 'The height of the monitor in pixels when using new menu (Top/Bottom)',
  })
  comfy.settings.declare({
    id: settings.legacyHeight, name: 'Pixel Height (Legacy Menu)', type: 'slider', defaultValue: 19,
    attrs: { min: 16, max: 50, step: 1 }, category: category('Configuration', 'height-legacy'),
    tooltip: 'The height of the monitor in pixels when using legacy menu (Disabled)',
  })
  comfy.settings.declare({
    id: settings.disableSmooth, name: 'Disable Smooth Animation', type: 'boolean',
    defaultValue: false, category: category('Configuration', 'refresh-smooth'),
    tooltip: 'When enabled, bars update instantly without smooth transitions',
  })
  comfy.settings.declare({
    id: settings.numbersOnly, name: 'Show Numbers Only', type: 'boolean',
    defaultValue: false, category: category('Configuration', 'refresh-text'),
    tooltip: 'When enabled, hides the colored bar and shows only the numeric value',
  })
  for (const [id, name, defaultValue, group] of [
    [settings.cpu, 'CPU Usage', true, 'Cpu'],
    [settings.ram, 'RAM Used', true, 'Ram'],
    [settings.hdd, 'Show HDD Used', false, 'Show'],
  ]) {
    comfy.settings.declare({
      id, name, type: 'boolean', defaultValue,
      category: category(group === 'Show' ? 'Show Hard Disk' : 'Hardware', group),
      onChange: () => updateBadges(),
    })
  }
}

function declareSnapshotSettings(snapshot) {
  const volumes = snapshot.volumes.map(({ id, label }) => ({ value: id, label }))
  comfy.settings.declare({
    id: settings.volume, name: 'Partition to show', type: 'combo',
    defaultValue: volumes[0]?.value ?? 'unavailable', options: volumes,
    category: ['CrysMonitor', 'Show Hard Disk', 'Which'],
    onChange: () => updateBadges(),
  })
  snapshot.accelerators.forEach((accelerator, index) => {
    const single = snapshot.accelerators.length === 1
    const group = single ? 'Show GPU' : `Show GPU ${index}`
    for (const [id, name, item] of [
      [`CrysMonitor.ShowGpuUsage${index}`, single ? ' Usage' : ` Usage (GPU ${index})`, 'Usage'],
      [`CrysMonitor.ShowGpuVram${index}`, single ? 'VRAM' : `VRAM (GPU ${index})`, 'VRAM'],
      [`CrysMonitor.ShowGpuTemperature${index}`, single ? 'Temperature' : `Temperature (GPU ${index})`, 'Temperature'],
    ]) {
      comfy.settings.declare({
        id, name, type: 'boolean', defaultValue: true,
        category: ['CrysMonitor', group, item],
        tooltip: `${index}: ${accelerator.name}`,
        onChange: () => updateBadges(),
      })
    }
  })
}

async function poll() {
  if (state.polling) return
  state.polling = true
  try {
    state.snapshot = await comfy.system.monitor()
    updateBadges()
  } finally {
    state.polling = false
  }
}

function resetVisibleValues() {
  if (!state.snapshot) return
  const zero = {
    cpu: { utilization_percent: 0 },
    memory: { total: 0, available: 0 },
    volumes: state.snapshot.volumes.map((volume) => ({ ...volume, total: 0, available: 0 })),
    accelerators: state.snapshot.accelerators.map((accelerator) => ({
      ...accelerator, memory_total: 0, memory_available: 0,
      utilization_percent: 0, temperature_c: 0,
    })),
  }
  updateBadges(zero)
}

function restartPolling() {
  if (state.timer !== undefined) clearInterval(state.timer)
  state.timer = undefined
  const seconds = Number(comfy.settings.get(settings.rate) ?? 1)
  if (seconds <= 0) {
    resetVisibleValues()
    return
  }
  void poll()
  state.timer = setInterval(() => void poll(), Math.max(250, seconds * 1000))
}

async function setup() {
  if (state.ready) return
  state.ready = true
  declareBaseSettings()
  state.snapshot = await comfy.system.monitor()
  declareSnapshotSettings(state.snapshot)
  updateBadges()
  restartPolling()
}

comfy.onReady(() => void setup())
