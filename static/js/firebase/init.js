import { initializeApp } from 'https://www.gstatic.com/firebasejs/9.22.1/firebase-app.js';
import { getAuth, onAuthStateChanged } from 'https://www.gstatic.com/firebasejs/9.22.1/firebase-auth.js';
import { getFirestore, enableIndexedDbPersistence } from 'https://www.gstatic.com/firebasejs/9.22.1/firebase-firestore.js';
import { getStorage } from 'https://www.gstatic.com/firebasejs/9.22.1/firebase-storage.js';
import { FIREBASE_CONFIG } from './config.js';

const app = initializeApp(FIREBASE_CONFIG);
export const auth = getAuth(app);
export const db = getFirestore(app);
export const storage = getStorage(app);

enableIndexedDbPersistence(db).catch((error) => {
  console.warn('Firestore persistence is unavailable:', error);
});

onAuthStateChanged(auth, (user) => {
  window.appUser = user;
  if (user) {
    console.log('Firebase user signed in:', user.uid);
  } else {
    console.log('No Firebase user signed in');
  }
});
