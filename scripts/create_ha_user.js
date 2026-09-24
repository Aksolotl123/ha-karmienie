// Zakłada osobne konto Firebase (e-mail/hasło) dla integracji Home Assistant „karmienie”
// i daje mu dostęp do /feedings (users/{uid}: allowed=true, appVersion=99999).
//
// Użycie (z katalogu repo):
//   GOOGLE_APPLICATION_CREDENTIALS=<plik klucza service account> \
//   FIREBASE_DATABASE_URL=<adres Realtime Database> \
//   node scripts/create_ha_user.js [email]
// ID projektu jest brane z pliku klucza. Skrypt jest idempotentny: przy ponownym
// uruchomieniu ustawia nowe hasło istniejącemu kontu.

const path = require('path');
const crypto = require('crypto');

const FUNCTIONS_MODULES = path.join(__dirname, '..', '..', 'functions', 'node_modules');
const admin = require(path.join(FUNCTIONS_MODULES, 'firebase-admin'));
const { GoogleAuth } = require(path.join(FUNCTIONS_MODULES, 'google-auth-library'));

const CREDS_PATH = process.env.GOOGLE_APPLICATION_CREDENTIALS;
const DATABASE_URL = process.env.FIREBASE_DATABASE_URL;
if (!CREDS_PATH || !DATABASE_URL) {
  console.error('Ustaw zmienne GOOGLE_APPLICATION_CREDENTIALS i FIREBASE_DATABASE_URL.');
  process.exit(1);
}
const SERVICE_ACCOUNT = require(path.resolve(CREDS_PATH));
const PROJECT_ID = SERVICE_ACCOUNT.project_id;
const EMAIL = process.argv[2] || 'home-assistant@karmienie.local';
// Powyżej każdego realnego versionCode — reguła appVersion >= minVersionCode zawsze przejdzie.
// Aplikacja Android nadpisuje appVersion tylko własnego użytkownika, więc ta wartość zostaje.
const APP_VERSION = 99999;

async function ensureEmailPasswordEnabled() {
  const auth = new GoogleAuth({
    keyFile: CREDS_PATH,
    scopes: ['https://www.googleapis.com/auth/cloud-platform'],
  });
  const client = await auth.getClient();
  const url = `https://identitytoolkit.googleapis.com/admin/v2/projects/${PROJECT_ID}/config`;
  const { data } = await client.request({ url });
  if (data?.signIn?.email?.enabled && data.signIn.email.passwordRequired !== false) {
    console.log('Logowanie e-mail/hasło: już włączone');
    return;
  }
  await client.request({
    url: `${url}?updateMask=signIn.email.enabled,signIn.email.passwordRequired`,
    method: 'PATCH',
    data: { signIn: { email: { enabled: true, passwordRequired: true } } },
  });
  console.log('Logowanie e-mail/hasło: WŁĄCZONE');
}

async function main() {
  admin.initializeApp({
    credential: admin.credential.cert(SERVICE_ACCOUNT),
    databaseURL: DATABASE_URL,
  });

  try {
    await ensureEmailPasswordEnabled();
  } catch (err) {
    console.warn(
      `Nie udało się sprawdzić/włączyć logowania e-mail/hasło (${err.message}).\n` +
        'Włącz ręcznie: Firebase Console → Authentication → Sign-in method → Email/Password.'
    );
  }

  const password = crypto.randomBytes(18).toString('base64url');
  let user;
  try {
    user = await admin.auth().getUserByEmail(EMAIL);
    await admin.auth().updateUser(user.uid, { password, disabled: false });
    console.log(`Konto istniało — ustawiono nowe hasło (uid ${user.uid})`);
  } catch (err) {
    if (err.code !== 'auth/user-not-found') throw err;
    user = await admin.auth().createUser({
      email: EMAIL,
      password,
      displayName: 'Home Assistant',
      emailVerified: true,
    });
    console.log(`Utworzono konto (uid ${user.uid})`);
  }

  // Konto admina omija reguły, w tym .validate blokujące zmianę „allowed” z klienta.
  await admin.database().ref(`users/${user.uid}`).update({
    allowed: true,
    appVersion: APP_VERSION,
    displayName: 'Home Assistant',
    platform: 'home-assistant',
  });
  const check = (await admin.database().ref(`users/${user.uid}`).once('value')).val();
  console.log(`users/${user.uid}:`, JSON.stringify(check));

  console.log('\nWpisz w Home Assistant (Ustawienia → Urządzenia i usługi → Dodaj → Karmienie Dziecka):');
  console.log(`  E-mail: ${EMAIL}`);
  console.log(`  Hasło:  ${password}`);
  await admin.app().delete();
}

main().catch((err) => {
  console.error('BŁĄD:', err.message || err);
  process.exit(1);
});
