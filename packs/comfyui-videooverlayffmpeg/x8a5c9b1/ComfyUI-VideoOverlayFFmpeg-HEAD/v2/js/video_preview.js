import { comfy } from '/comfy/api/v2.js';


const TYPES = ['VideoOverlayNode', 'VideoOverlayWithSubtitlesNode'];


function firstVideo(result) {
  const values = result?.raw?.videos ?? result?.raw?.gifs ?? result?.videos ?? result?.gifs;
  const item = Array.isArray(values) ? values[0] : undefined;
  if (typeof item === 'string') {
    return { filename: item, type: 'output', subfolder: '' };
  }
  return item && typeof item === 'object' ? item : undefined;
}


function videoUrl(record) {
  const params = new URLSearchParams({
    filename: String(record.filename ?? ''),
    type: String(record.type ?? 'output'),
    subfolder: String(record.subfolder ?? ''),
  });
  return comfy.backend.url(`/view?${params.toString()}`);
}


for (const type of TYPES) {
  comfy.defs.extend(type, (builder) => {
    builder.onExecuted((node, result) => {
      const record = firstVideo(result);
      if (!record?.filename) return;

      const name = 'video_overlay_preview';
      node.widgets.remove(name);
      node.widgets.mount({
        name,
        defaultValue: videoUrl(record),
        serialize: false,
        render(container) {
          container.style.width = '100%';
          container.style.minHeight = '100px';
          container.style.overflow = 'hidden';
          container.style.borderRadius = '4px';

          const video = document.createElement('video');
          video.src = videoUrl(record);
          video.loop = true;
          video.muted = true;
          video.preload = 'metadata';
          video.style.width = '100%';
          video.style.display = 'block';
          video.style.background = '#000';
          video.style.cursor = 'pointer';
          video.addEventListener('mouseenter', () => {
            video.muted = false;
            void video.play().catch(() => {
              video.muted = true;
              return video.play();
            });
          });
          video.addEventListener('mouseleave', () => {
            video.pause();
            video.muted = true;
          });
          video.addEventListener('click', (event) => {
            event.stopPropagation();
            if (video.paused) void video.play();
            else video.pause();
          });
          container.append(video);
        },
      });
      node.setSizeConstraints({ minWidth: 350, autoHeight: true });
    });
  });
}
