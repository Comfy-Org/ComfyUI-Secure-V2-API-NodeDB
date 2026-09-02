import { comfy } from '/comfy/api/v2.js';

const NODE = 'vsLinx_GroupBookmarks';
let refreshPanel = () => {};

function migrate(raw) {
  if (!Array.isArray(raw)) return [];
  const output = [];
  const add = (item) => {
    if (typeof item === 'string') output.push({ type: 'group', title: item });
    else if (item?.type === 'node' && item.nodeId != null) {
      output.push({ type: 'node', nodeId: String(item.nodeId), name: String(item.name ?? ''), parent: String(item.parent ?? '') });
    } else if (item?.type === 'section' || item?.type === 'headline') {
      output.push({ type: 'section', label: String(item.label ?? item.name ?? '') });
      if (Array.isArray(item.children)) item.children.forEach(add);
    } else if (item?.type === 'group' || item?.title != null) {
      output.push({ type: 'group', title: String(item.title ?? '') });
    }
  };
  raw.forEach(add);
  return output.slice(0, 1024);
}

function bookmarkNodes() {
  return comfy.graph.queryNodes({ type: NODE, scope: 'root-and-subgraphs' });
}

function itemsAcrossNodes() {
  const groups = new Set();
  const nodes = new Set();
  const result = [];
  for (const owner of bookmarkNodes()) {
    for (const item of migrate(owner.getProperty('bookmarks'))) {
      if (item.type === 'section') result.push(item);
      else if (item.type === 'group' && !groups.has(item.title)) {
        groups.add(item.title); result.push(item);
      } else if (item.type === 'node' && !nodes.has(item.nodeId)) {
        nodes.add(item.nodeId); result.push(item);
      }
    }
  }
  return result;
}

function nodeById(id) {
  return comfy.graph.queryNodes({ scope: 'root-and-subgraphs' })
    .find((node) => String(node.id) === String(id));
}

function button(doc, label, run) {
  const value = doc.createElement('button');
  value.textContent = label;
  value.addEventListener('click', run);
  return value;
}

function renderPanel(container) {
  const doc = container.ownerDocument;
  const draw = () => {
    container.replaceChildren();
    const items = itemsAcrossNodes();
    if (!items.length) {
      const empty = doc.createElement('p');
      empty.textContent = 'Add a Group Bookmarks node, then choose Manage Bookmarks.';
      empty.style.opacity = '0.7';
      container.append(empty);
      return;
    }
    const collapsed = new Set(
      bookmarkNodes().flatMap((node) => Array.isArray(node.getProperty('collapsedSections'))
        ? node.getProperty('collapsedSections').map(String) : []),
    );
    let hidden = false;
    for (const item of items) {
      if (item.type === 'section') {
        hidden = collapsed.has(item.label);
        const section = button(doc, `${hidden ? '▸' : '▾'} ${item.label || 'Section'}`, () => {
          if (collapsed.has(item.label)) collapsed.delete(item.label); else collapsed.add(item.label);
          for (const node of bookmarkNodes()) node.setProperty('collapsedSections', [...collapsed]);
          draw();
        });
        Object.assign(section.style, { display: 'block', width: '100%', textAlign: 'left', marginTop: '8px' });
        container.append(section);
        continue;
      }
      if (hidden) continue;
      let label;
      let run;
      if (item.type === 'group') {
        const group = comfy.graph.groups().find((candidate) => candidate.getTitle() === item.title);
        label = group ? `▣ ${group.getTitle()}` : `▣ ${item.title} (missing)`;
        run = () => group?.centerOn();
      } else {
        const node = nodeById(item.nodeId);
        label = node ? `● ${node.getTitle()}` : `● ${item.name || item.nodeId} (missing)`;
        run = () => {
          if (!node) return;
          comfy.graph.centerOn(node);
          comfy.graph.select([node]);
        };
      }
      const entry = button(doc, label, run);
      Object.assign(entry.style, {
        display: 'block', width: '100%', textAlign: 'left', margin: '3px 0',
        opacity: label.endsWith('(missing)') ? '0.45' : '1',
      });
      container.append(entry);
    }
  };
  refreshPanel = draw;
  draw();
}

function manage(owner) {
  let items = migrate(owner.getProperty('bookmarks'));
  let handle;
  handle = comfy.ui.showDialog({
    key: `vslinx.bookmarks.${owner.graphId ?? 'graph'}.${owner.id}`,
    title: 'Manage Bookmarks',
    render(container) {
      const doc = container.ownerDocument;
      Object.assign(container.style, { minWidth: '620px', maxWidth: '90vw' });
      const columns = doc.createElement('div');
      Object.assign(columns.style, { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' });
      const available = doc.createElement('div');
      const active = doc.createElement('div');
      columns.append(available, active);
      container.append(columns);

      const isPresent = (candidate) => items.some((item) =>
        candidate.type === 'group'
          ? item.type === 'group' && item.title === candidate.title
          : item.type === 'node' && String(item.nodeId) === String(candidate.nodeId));

      const renderAvailable = () => {
        available.replaceChildren();
        const title = doc.createElement('h3'); title.textContent = 'Groups & nodes'; available.append(title);
        for (const group of comfy.graph.groups()) {
          const candidate = { type: 'group', title: group.getTitle() };
          const add = button(doc, `▣ ${candidate.title}`, () => {
            if (!isPresent(candidate)) items.push(candidate);
            renderAvailable(); renderActive();
          });
          add.disabled = isPresent(candidate);
          available.append(add, doc.createElement('br'));
          for (const node of group.nodes().filter((value) => value.type !== NODE)) {
            const nodeItem = { type: 'node', nodeId: String(node.id), name: node.getTitle(), parent: group.getTitle() };
            const addNode = button(doc, `  ● ${node.getTitle()}`, () => {
              if (!isPresent(nodeItem)) items.push(nodeItem);
              renderAvailable(); renderActive();
            });
            addNode.disabled = isPresent(nodeItem);
            addNode.style.marginLeft = '18px';
            available.append(addNode, doc.createElement('br'));
          }
        }
        const grouped = new Set(comfy.graph.groups().flatMap((group) => group.nodes().map((node) => node.id)));
        for (const node of comfy.graph.nodes().filter((value) => value.type !== NODE && !grouped.has(value.id))) {
          const candidate = { type: 'node', nodeId: String(node.id), name: node.getTitle(), parent: '' };
          const add = button(doc, `● ${node.getTitle()}`, () => {
            if (!isPresent(candidate)) items.push(candidate);
            renderAvailable(); renderActive();
          });
          add.disabled = isPresent(candidate);
          available.append(add, doc.createElement('br'));
        }
      };

      const renderActive = () => {
        active.replaceChildren();
        const title = doc.createElement('h3'); title.textContent = 'Active bookmarks'; active.append(title);
        items.forEach((item, index) => {
          const row = doc.createElement('div');
          Object.assign(row.style, { display: 'flex', gap: '4px', margin: '4px 0' });
          let label;
          if (item.type === 'section') {
            label = doc.createElement('input');
            label.value = item.label;
            label.addEventListener('input', () => { item.label = label.value.slice(0, 128); });
          } else {
            label = doc.createElement('span');
            label.textContent = item.type === 'group' ? `▣ ${item.title}` : `● ${item.name || item.nodeId}`;
            label.style.flex = '1';
          }
          const up = button(doc, '↑', () => {
            if (index > 0) [items[index - 1], items[index]] = [items[index], items[index - 1]];
            renderActive();
          });
          const down = button(doc, '↓', () => {
            if (index + 1 < items.length) [items[index], items[index + 1]] = [items[index + 1], items[index]];
            renderActive();
          });
          const remove = button(doc, '×', () => {
            items.splice(index, 1); renderAvailable(); renderActive();
          });
          row.append(label, up, down, remove);
          active.append(row);
        });
      };

      const controls = doc.createElement('div');
      Object.assign(controls.style, { display: 'flex', justifyContent: 'space-between', marginTop: '14px' });
      controls.append(
        button(doc, '+ Add section', () => { items.push({ type: 'section', label: 'Section' }); renderActive(); }),
        button(doc, 'Confirm', () => {
          owner.setProperty('bookmarks', items);
          refreshPanel();
          handle.close();
        }),
      );
      container.append(controls);
      renderAvailable(); renderActive();
    },
  });
}

comfy.ui.addSidebarTab({
  id: 'vslinx.groupBookmarks',
  title: 'Bookmarks',
  icon: 'icon-[lucide--bookmark]',
  render: renderPanel,
});

comfy.defs.extend(NODE, (builder) => {
  builder.onCreated((node) => {
    node.setProperty('bookmarks', migrate(node.getProperty('bookmarks')));
    const manageButton = node.widgets.add({ type: 'button', name: 'Manage Bookmarks', serialize: false });
    manageButton.on('activate', () => manage(node));
    node.setSizeConstraints({ autoHeight: true });
    refreshPanel();
  });
  builder.onConfigured((node) => {
    node.setProperty('bookmarks', migrate(node.getProperty('bookmarks')));
    refreshPanel();
  });
  builder.onRemoved(() => refreshPanel());
});

comfy.onWorkflowLoaded(refreshPanel);
comfy.onNodeChanged(refreshPanel, { scope: 'document' });
