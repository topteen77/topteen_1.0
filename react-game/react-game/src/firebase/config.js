// Firebase Configuration
import { initializeApp } from 'firebase/app';
import { getFunctions, connectFunctionsEmulator } from 'firebase/functions';

// Your Firebase configuration
// Replace these with your actual Firebase project config
const firebaseConfig = {
  apiKey: "AIzaSyBeHXYZ1wI8C2fTGO-V2KWZa9eA4jsYUe4",
  authDomain: "gen-lang-client-0869533322.firebaseapp.com",
  projectId: "gen-lang-client-0869533322",
  storageBucket: "gen-lang-client-0869533322.firebasestorage.app",
  messagingSenderId: "193850341205",
  appId: "1:193850341205:web:c8bedad67e9c49354f61dc",
  measurementId: "G-WYW9C5F3VK"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Cloud Functions with region
// Use 'us-central1' to match your Firebase function deployment region
const functions = getFunctions(app, 'us-central1');

// Connect to emulator in development (optional)
// Uncomment if using Firebase emulators locally
// if (import.meta.env.DEV) {
//   connectFunctionsEmulator(functions, 'localhost', 5001);
// }

export { app, functions };
export default app;

