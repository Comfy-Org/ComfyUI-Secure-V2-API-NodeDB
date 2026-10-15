import { comfy } from '/comfy/api/v2.js'
import { refreshAudioModelUnion } from './wan_audio_catalogue_options.js'

for (const nodeType of ['MultiTalkModelLoader', 'OviMMAudioVAELoader']) {
  comfy.defs.extend(nodeType, builder => {
    const refresh = node => {
      void refreshAudioModelUnion(comfy, node, nodeType).catch(error => {
        console.warn('Wan audio model menu refresh failed', error)
      })
    }
    builder.onCreated(refresh)
    builder.onConfigured(refresh)
    builder.addMenuItem({label: 'Refresh model list', run: refresh})
  })
}
