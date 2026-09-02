import { comfy } from '/comfy/api/v2.js';


const BASE64_URL =
  'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';


function randomProvider() {
  const provider = globalThis.crypto;
  if (!provider || typeof provider.getRandomValues !== 'function') {
    throw new Error('Secure randomness is unavailable in this sandbox.');
  }
  return provider;
}


function concatBytes(...parts) {
  const length = parts.reduce((total, part) => total + part.byteLength, 0);
  const joined = new Uint8Array(length);
  let offset = 0;
  for (const part of parts) {
    joined.set(part, offset);
    offset += part.byteLength;
  }
  return joined;
}


function base64UrlEncode(bytes) {
  let encoded = '';
  for (let offset = 0; offset < bytes.byteLength; offset += 3) {
    const first = bytes[offset];
    const hasSecond = offset + 1 < bytes.byteLength;
    const hasThird = offset + 2 < bytes.byteLength;
    const second = hasSecond ? bytes[offset + 1] : 0;
    const third = hasThird ? bytes[offset + 2] : 0;
    const value = (first << 16) | (second << 8) | third;
    encoded += BASE64_URL[(value >>> 18) & 63];
    encoded += BASE64_URL[(value >>> 12) & 63];
    encoded += hasSecond ? BASE64_URL[(value >>> 6) & 63] : '=';
    encoded += hasThird ? BASE64_URL[value & 63] : '=';
  }
  return encoded;
}


function base64Value(character) {
  const value = BASE64_URL.indexOf(character);
  if (value < 0) throw new TypeError('Invalid URL-safe base64 data.');
  return value;
}


function base64UrlDecode(value) {
  if (typeof value !== 'string') {
    throw new TypeError('URL-safe base64 data must be a string.');
  }
  const trimmed = value.trim();
  const raw = trimmed.replace(/=+$/, '');
  const suppliedPadding = trimmed.length - raw.length;
  if (!raw || suppliedPadding > 2 || raw.includes('=') ||
      !/^[A-Za-z0-9_-]+$/.test(raw) || raw.length % 4 === 1) {
    throw new TypeError('Invalid URL-safe base64 data.');
  }
  const requiredPadding = (4 - (raw.length % 4)) % 4;
  if (suppliedPadding !== 0 && suppliedPadding !== requiredPadding) {
    throw new TypeError('Invalid URL-safe base64 padding.');
  }
  const padded = raw + '='.repeat(requiredPadding);
  const outputLength = (padded.length / 4) * 3 - requiredPadding;
  const output = new Uint8Array(outputLength);
  let outputOffset = 0;
  for (let offset = 0; offset < padded.length; offset += 4) {
    const a = base64Value(padded[offset]);
    const b = base64Value(padded[offset + 1]);
    const c = padded[offset + 2] === '=' ? 0 : base64Value(padded[offset + 2]);
    const d = padded[offset + 3] === '=' ? 0 : base64Value(padded[offset + 3]);
    const combined = (a << 18) | (b << 12) | (c << 6) | d;
    if (outputOffset < outputLength) output[outputOffset++] = combined >>> 16;
    if (outputOffset < outputLength) output[outputOffset++] = combined >>> 8;
    if (outputOffset < outputLength) output[outputOffset++] = combined;
  }
  if (base64UrlEncode(output).replace(/=+$/, '') !== raw) {
    throw new TypeError('Non-canonical URL-safe base64 data.');
  }
  return output;
}


function timestampBytes(milliseconds) {
  let value = BigInt(Math.floor(milliseconds / 1000));
  if (value < 0n || value > 0xffffffffffffffffn) {
    throw new RangeError('Fernet timestamp is out of range.');
  }
  const result = new Uint8Array(8);
  for (let index = result.length - 1; index >= 0; index -= 1) {
    result[index] = Number(value & 0xffn);
    value >>= 8n;
  }
  return result;
}


function decodedToken(token) {
  const bytes = base64UrlDecode(token);
  const ciphertextLength = bytes.byteLength - 1 - 8 - 16 - 32;
  if (bytes.byteLength < 73 || bytes[0] !== 0x80 ||
      ciphertextLength < 16 || ciphertextLength % 16 !== 0) {
    throw new TypeError('Invalid Fernet token structure.');
  }
  return bytes;
}


function decodedKey(key) {
  const bytes = base64UrlDecode(key);
  if (bytes.byteLength !== 32) {
    throw new TypeError('A Fernet key must contain exactly 32 bytes.');
  }
  return bytes;
}


function randomBytes(length) {
  const bytes = new Uint8Array(length);
  randomProvider().getRandomValues(bytes);
  return bytes;
}


export function fernetTokenFromBytes(bytes) {
  if (!(bytes instanceof Uint8Array)) {
    throw new TypeError('Encrypted workflow data must be bytes.');
  }
  for (const byte of bytes) {
    if (byte > 0x7f) {
      throw new TypeError('A Fernet token must be URL-safe ASCII.');
    }
  }
  const token = new TextDecoder('utf-8', { fatal: true }).decode(bytes).trim();
  decodedToken(token);
  return token;
}


export function looksLikeFernetToken(bytes) {
  try {
    fernetTokenFromBytes(bytes);
    return true;
  } catch {
    return false;
  }
}


export async function encryptFernet(plaintext) {
  if (!(plaintext instanceof Uint8Array)) {
    throw new TypeError('Fernet plaintext must be bytes.');
  }
  const key = randomBytes(32);
  const signingKey = key.slice(0, 16);
  const encryptionKey = key.slice(16);
  const iv = randomBytes(16);
  const ciphertext = await comfy.crypto.aesCbcEncrypt({
    key: encryptionKey,
    iv,
    plaintext,
  });
  const signed = concatBytes(
    new Uint8Array([0x80]), timestampBytes(Date.now()), iv, ciphertext);
  const signature = await comfy.crypto.hmacSha256({
    key: signingKey,
    data: signed,
  });
  return {
    key: base64UrlEncode(key),
    token: base64UrlEncode(concatBytes(signed, signature)),
  };
}


export async function decryptFernet(token, key) {
  const keyBytes = decodedKey(key);
  const tokenBytes = decodedToken(token);
  const signed = tokenBytes.slice(0, -32);
  const signature = tokenBytes.slice(-32);
  const valid = await comfy.crypto.verifyHmacSha256({
    key: keyBytes.slice(0, 16),
    data: signed,
    signature,
  });
  if (!valid) throw new Error('Fernet authentication failed.');

  const iv = tokenBytes.slice(9, 25);
  const ciphertext = tokenBytes.slice(25, -32);
  try {
    return await comfy.crypto.aesCbcDecrypt({
      key: keyBytes.slice(16),
      iv,
      ciphertext,
    });
  } catch {
    throw new Error('Fernet decryption failed.');
  }
}
