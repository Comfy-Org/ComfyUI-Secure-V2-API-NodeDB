import { comfy } from '/comfy/api/v2.js';

import {
  decryptFernet,
  encryptFernet,
  fernetTokenFromBytes,
  looksLikeFernetToken,
} from './fernet.js';


const SAVE_COMMAND = 'ComfyWorkflowEncrypt.saveEncrypted';
const LOAD_COMMAND = 'ComfyWorkflowEncrypt.loadDecrypted';
const MAX_WORKFLOW_BYTES = 8 * 1024 * 1024;
const MAX_ENCRYPTED_BYTES = 16 * 1024 * 1024;
const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder('utf-8', { fatal: true });


function workflowBytes(workflow) {
  const encoded = textEncoder.encode(JSON.stringify(workflow));
  if (encoded.byteLength > MAX_WORKFLOW_BYTES) {
    throw new RangeError('The workflow is too large to encrypt.');
  }
  return encoded;
}


function workflowFromBytes(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.byteLength > MAX_WORKFLOW_BYTES) {
    throw new RangeError('The decrypted workflow is too large.');
  }
  const workflow = JSON.parse(textDecoder.decode(bytes));
  if (!workflow || typeof workflow !== 'object' || Array.isArray(workflow)) {
    throw new TypeError('The encrypted file does not contain a workflow object.');
  }
  return workflow;
}


function notifyError(summary, detail) {
  comfy.commands.notify({ severity: 'error', summary, detail });
}


async function showKey(key) {
  await comfy.ui.prompt({
    label: 'Save this workflow encryption key before closing; it is shown once',
    value: key,
  });
}


async function decryptWorkflow(bytes, key) {
  const token = fernetTokenFromBytes(bytes);
  const plaintext = await decryptFernet(token, key.trim());
  return workflowFromBytes(plaintext);
}


export async function saveEncryptedWorkflow() {
  try {
    const workflow = await comfy.workflow.snapshot();
    const { key, token } = await encryptFernet(workflowBytes(workflow));
    const bytes = textEncoder.encode(token);
    if (bytes.byteLength > MAX_ENCRYPTED_BYTES) {
      throw new RangeError('The encrypted workflow is too large to download.');
    }
    // Preserve upstream's ordering: the user sees and can store the one-time
    // key before the encrypted file is handed to the browser download UI.
    await showKey(key);
    await comfy.files.download({
      name: 'encrypted_data.txt',
      mimeType: 'text/plain',
      bytes,
    });
  } catch (error) {
    notifyError(
      'Workflow encryption failed',
      error instanceof Error ? error.message : 'Unable to encrypt this workflow.',
    );
  }
}


export async function loadEncryptedWorkflow() {
  const key = await comfy.ui.prompt({
    label: 'Workflow decryption key',
    placeholder: 'Paste the key that was shown when the workflow was encrypted',
  });
  if (key === undefined) return;

  const selected = await comfy.files.pick({
    extensions: ['txt'],
    mimeTypes: ['text/plain'],
    maxBytes: MAX_ENCRYPTED_BYTES,
  });
  if (!selected) return;

  try {
    if (!looksLikeFernetToken(selected.bytes)) {
      throw new TypeError('The selected file is not a Fernet encrypted workflow.');
    }
    await comfy.workflow.open(await decryptWorkflow(selected.bytes, key));
  } catch {
    notifyError(
      'Workflow decryption failed',
      'The key does not match the file, or the encrypted file is damaged.',
    );
  }
}


comfy.commands.register({
  id: SAVE_COMMAND,
  label: 'Save (Encrypted)',
  run: saveEncryptedWorkflow,
});

comfy.commands.register({
  id: LOAD_COMMAND,
  label: 'Load (Decrypted)',
  run: loadEncryptedWorkflow,
});

comfy.ui.addActionBarButton({
  id: SAVE_COMMAND,
  icon: 'pi-lock',
  label: 'Save (Encrypted)',
  tooltip: 'Download an encrypted copy of the current workflow',
  run: () => comfy.commands.run(SAVE_COMMAND),
});

comfy.ui.addActionBarButton({
  id: LOAD_COMMAND,
  icon: 'pi-lock-open',
  label: 'Load (Decrypted)',
  tooltip: 'Decrypt and open a workflow file',
  run: () => comfy.commands.run(LOAD_COMMAND),
});


// Native Open Workflow and drag/drop reach the same worker-side parser.  A
// structurally unrelated text file returns null so ComfyUI's normal importer
// remains the fallback.
comfy.workflow.registerImporter({
  id: 'ComfyWorkflowEncrypt.fernet',
  mimeTypes: ['text/plain'],
  extensions: ['txt'],
  maxBytes: MAX_ENCRYPTED_BYTES,
  enabled: () => true,
  async parse(bytes) {
    if (!looksLikeFernetToken(bytes)) return null;
    const key = await comfy.ui.prompt({
      label: 'Workflow decryption key',
      placeholder: 'Paste the key for this encrypted workflow',
    });
    if (key === undefined) return null;
    try {
      return { workflow: await decryptWorkflow(bytes, key) };
    } catch {
      notifyError(
        'Workflow decryption failed',
        'The key does not match the file, or the encrypted file is damaged.',
      );
      return null;
    }
  },
});
