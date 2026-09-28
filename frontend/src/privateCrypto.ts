// Шифрование приватных записей в браузере (D4, kognis-8f1): PBKDF2-SHA256 → AES-GCM-256 (WebCrypto).
// На сервер уходит только конверт `Envelope`; пароль и открытый текст устройство не покидают.
// Пароль восстановить нельзя: ключ существует только у того, кто его знает.

export const FORMAT_VERSION = 1;
export const KDF_NAME = "PBKDF2-SHA256";
export const KDF_ITERATIONS = 600_000;
export const MIN_PRIVATE_PASSWORD = 8;
const SALT_BYTES = 16;
const IV_BYTES = 12;
// версия формата привязана к шифртексту: подмена заголовка конверта расшифровку не пройдёт
const AAD = new TextEncoder().encode(`kognis-private-v${FORMAT_VERSION}`);

export interface Envelope {
  v: number;
  kdf: string;
  iter: number;
  salt: string;
  iv: string;
  ct: string;
}

export class WrongPasswordError extends Error {
  constructor() {
    super("Неверный пароль или запись повреждена. Пароль восстановить нельзя.");
  }
}

export class UnsupportedFormatError extends Error {
  constructor() {
    super("Запись создана в неизвестном формате — обновите приложение.");
  }
}

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function fromBase64(text: string): Uint8Array<ArrayBuffer> {
  const binary = atob(text);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

async function deriveKey(
  password: string,
  salt: Uint8Array<ArrayBuffer>,
  iterations: number,
): Promise<CryptoKey> {
  const material = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveKey"],
  );
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

export async function encryptText(password: string, text: string): Promise<Envelope> {
  const salt = crypto.getRandomValues(new Uint8Array(SALT_BYTES));
  const iv = crypto.getRandomValues(new Uint8Array(IV_BYTES));
  const key = await deriveKey(password, salt, KDF_ITERATIONS);
  const data = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv, additionalData: AAD },
    key,
    new TextEncoder().encode(text),
  );
  return {
    v: FORMAT_VERSION,
    kdf: KDF_NAME,
    iter: KDF_ITERATIONS,
    salt: toBase64(salt),
    iv: toBase64(iv),
    ct: toBase64(new Uint8Array(data)),
  };
}

export async function decryptText(password: string, envelope: Envelope): Promise<string> {
  if (envelope.v !== FORMAT_VERSION || envelope.kdf !== KDF_NAME)
    throw new UnsupportedFormatError();
  try {
    const key = await deriveKey(password, fromBase64(envelope.salt), envelope.iter);
    const data = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: fromBase64(envelope.iv), additionalData: AAD },
      key,
      fromBase64(envelope.ct),
    );
    return new TextDecoder().decode(data);
  } catch {
    // AES-GCM не отличает неверный ключ от порчи данных — говорим об обоих сразу
    throw new WrongPasswordError();
  }
}
