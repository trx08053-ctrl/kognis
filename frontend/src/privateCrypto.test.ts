import { expect, test } from "vitest";
import {
  decryptText,
  encryptText,
  FORMAT_VERSION,
  KDF_ITERATIONS,
  UnsupportedFormatError,
  WrongPasswordError,
} from "./privateCrypto";

const PASSWORD = "правильный-пароль";
const TEXT = "Секретная мысль про начальника 🔒";

test("шифрует и расшифровывает тем же паролем", async () => {
  const envelope = await encryptText(PASSWORD, TEXT);
  expect(envelope.v).toBe(FORMAT_VERSION);
  expect(envelope.kdf).toBe("PBKDF2-SHA256");
  expect(envelope.iter).toBe(KDF_ITERATIONS);
  expect(KDF_ITERATIONS).toBeGreaterThanOrEqual(600_000);
  expect(await decryptText(PASSWORD, envelope)).toBe(TEXT);
});

test("в конверте нет открытого текста и пароля", async () => {
  const envelope = await encryptText(PASSWORD, TEXT);
  const dump = JSON.stringify(envelope);
  expect(dump).not.toContain("Секретная");
  expect(dump).not.toContain(PASSWORD);
  expect(atob(envelope.ct)).not.toContain("Секретная");
});

test("соль и iv случайны: один текст даёт разные конверты", async () => {
  const a = await encryptText(PASSWORD, TEXT);
  const b = await encryptText(PASSWORD, TEXT);
  expect(a.salt).not.toBe(b.salt);
  expect(a.iv).not.toBe(b.iv);
  expect(a.ct).not.toBe(b.ct);
});

test("неверный пароль — понятная ошибка", async () => {
  const envelope = await encryptText(PASSWORD, TEXT);
  await expect(decryptText("другой-пароль-1", envelope)).rejects.toBeInstanceOf(WrongPasswordError);
  await expect(decryptText("другой-пароль-1", envelope)).rejects.toThrow(/Неверный пароль/);
});

test("порча шифртекста обнаруживается", async () => {
  const envelope = await encryptText(PASSWORD, TEXT);
  const raw = atob(envelope.ct);
  const flipped = String.fromCharCode(raw.charCodeAt(0) ^ 1);
  const broken = { ...envelope, ct: btoa(flipped + raw.slice(1)) };
  await expect(decryptText(PASSWORD, broken)).rejects.toBeInstanceOf(WrongPasswordError);
});

test("неизвестная версия формата отклоняется без попытки расшифровки", async () => {
  const envelope = await encryptText(PASSWORD, TEXT);
  await expect(decryptText(PASSWORD, { ...envelope, v: 99 })).rejects.toBeInstanceOf(
    UnsupportedFormatError,
  );
});
