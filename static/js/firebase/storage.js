import { storage } from './init.js';
import { ref, uploadBytes, getDownloadURL } from 'https://www.gstatic.com/firebasejs/9.22.1/firebase-storage.js';

export async function uploadFile(path, file) {
  const storageRef = ref(storage, path);
  await uploadBytes(storageRef, file);
  return getDownloadURL(storageRef);
}

export async function getFileUrl(path) {
  const storageRef = ref(storage, path);
  return getDownloadURL(storageRef);
}
