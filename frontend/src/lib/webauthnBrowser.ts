// Bridges the JSON shape the backend speaks (base64url-encoded strings,
// matching the standard WebAuthn JSON convention) and the native
// navigator.credentials API, which works in raw ArrayBuffers. No WebAuthn
// npm library is used here — this is the full extent of encoding
// boilerplate needed to talk to the browser API directly.

function base64UrlToBuffer(base64url: string): ArrayBuffer {
  const padded = base64url.replace(/-/g, '+').replace(/_/g, '/').padEnd(base64url.length + ((4 - (base64url.length % 4)) % 4), '=');
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

function bufferToBase64Url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function isWebAuthnSupported(): boolean {
  return typeof window !== 'undefined' && !!window.PublicKeyCredential && !!navigator.credentials;
}

/** Whether this device actually has a fingerprint/face/PIN platform
   authenticator available — worth checking before showing the option at
   all, since offering it on a device with no biometric hardware just
   invites a confusing failure. */
export async function isPlatformAuthenticatorAvailable(): Promise<boolean> {
  if (!isWebAuthnSupported()) return false;
  try {
    return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
  } catch {
    return false;
  }
}

export async function performRegistration(optionsJson: Record<string, unknown>): Promise<Record<string, unknown>> {
  const publicKey = optionsJson as unknown as PublicKeyCredentialCreationOptions;
  const opts: PublicKeyCredentialCreationOptions = {
    ...publicKey,
    challenge: base64UrlToBuffer(optionsJson.challenge as string),
    user: {
      ...(optionsJson.user as { name: string; displayName: string }),
      id: base64UrlToBuffer((optionsJson.user as { id: string }).id),
    },
    excludeCredentials: ((optionsJson.excludeCredentials as { id: string; type: string }[]) || []).map((c) => ({
      ...c,
      id: base64UrlToBuffer(c.id),
    })),
  };

  const credential = (await navigator.credentials.create({ publicKey: opts })) as PublicKeyCredential | null;
  if (!credential) throw new Error('No credential returned');

  const response = credential.response as AuthenticatorAttestationResponse;
  return {
    id: credential.id,
    rawId: bufferToBase64Url(credential.rawId),
    type: credential.type,
    response: {
      clientDataJSON: bufferToBase64Url(response.clientDataJSON),
      attestationObject: bufferToBase64Url(response.attestationObject),
    },
  };
}

export async function performAuthentication(optionsJson: Record<string, unknown>): Promise<Record<string, unknown>> {
  const opts: PublicKeyCredentialRequestOptions = {
    ...(optionsJson as unknown as PublicKeyCredentialRequestOptions),
    challenge: base64UrlToBuffer(optionsJson.challenge as string),
    allowCredentials: ((optionsJson.allowCredentials as { id: string; type: string }[]) || []).map((c) => ({
      ...c,
      id: base64UrlToBuffer(c.id),
    })),
  };

  const credential = (await navigator.credentials.get({ publicKey: opts })) as PublicKeyCredential | null;
  if (!credential) throw new Error('No credential returned');

  const response = credential.response as AuthenticatorAssertionResponse;
  return {
    id: credential.id,
    rawId: bufferToBase64Url(credential.rawId),
    type: credential.type,
    response: {
      clientDataJSON: bufferToBase64Url(response.clientDataJSON),
      authenticatorData: bufferToBase64Url(response.authenticatorData),
      signature: bufferToBase64Url(response.signature),
      userHandle: response.userHandle ? bufferToBase64Url(response.userHandle) : null,
    },
  };
}
