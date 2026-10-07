import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { removeLegacyChatHistory } from './store/chatStore.simple'

// Chats now persist on the server. Drop any chat data the old localStorage
// store left behind before React renders.
removeLegacyChatHistory();

const root = createRoot(document.getElementById("root")!);
root.render(
  <StrictMode>
    <App />
  </StrictMode>
);
