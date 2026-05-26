import { db } from './init.js';
import { collection, getDocs, getDoc, doc, query, orderBy } from 'https://www.gstatic.com/firebasejs/9.22.1/firebase-firestore.js';

const productsCollection = collection(db, 'products');

export async function fetchProducts() {
  const q = query(productsCollection, orderBy('name'));
  const snapshot = await getDocs(q);
  return snapshot.docs.map((doc) => ({ id: doc.id, ...doc.data() }));
}

export async function fetchProductById(productId) {
  const docRef = doc(db, 'products', productId);
  const snapshot = await getDoc(docRef);
  return snapshot.exists() ? { id: snapshot.id, ...snapshot.data() } : null;
}
