import { comfy } from '/comfy/api/v2.js'
import { refreshAudioModelUnion } from './wan_audio_catalogue_options.js'

for (const nodeType of ['MultiTalkModelLoader', 'OviMMAudioVAELoader']) {
  comfy.defs.extend(nodeType, builder => {
    const refresh = (node, force = false) => {
      void refreshAudioModelUnion(comfy, node, nodeType, force).catch(error => {
        console.warn('Wan audio model menu refresh failed', error)
      })
    }
    builder.onCreated(node => refresh(node))
    builder.onConfigured(node => refresh(node))
    builder.addMenuItem({label: 'Refresh model list', run: node => refresh(node, true)})
  })
}
