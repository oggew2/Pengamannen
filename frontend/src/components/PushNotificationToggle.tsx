import { useState, useEffect } from 'react';
import { Box, HStack, Text, Button } from '@chakra-ui/react';
import { toaster } from './toaster';

// Convert base64 to Uint8Array for applicationServerKey
function urlBase64ToUint8Array(base64String: string): ArrayBuffer {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray.buffer;
}

export function PushNotificationToggle() {
  const [permission, setPermission] = useState<NotificationPermission>('default');
  const [subscribed, setSubscribed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [supported, setSupported] = useState(true);

  useEffect(() => {
    // Check if push is supported
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      setSupported(false);
      return;
    }
    
    setPermission(Notification.permission);
    
    // Check if already subscribed
    navigator.serviceWorker.ready.then((reg) => {
      reg.pushManager.getSubscription().then((sub) => {
        setSubscribed(!!sub);
      });
    });
  }, []);

  const subscribe = async () => {
    setLoading(true);
    try {
      // Request permission
      const perm = await Notification.requestPermission();
      setPermission(perm);
      
      if (perm !== 'granted') {
        toaster.create({ title: 'Notifikationer blockerade', type: 'warning', duration: 3000 });
        return;
      }
      
      // Get VAPID public key
      const keyRes = await fetch('/v1/push/vapid-key');
      const { publicKey } = await keyRes.json();
      
      // Subscribe
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      });
      
      // Send to backend
      const res = await fetch('/v1/push/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(sub.toJSON()),
      });
      
      if (res.ok) {
        setSubscribed(true);
        toaster.create({ title: '🔔 Notifikationer aktiverade!', type: 'success', duration: 3000 });
      }
    } catch (e) {
      console.error('Push subscription failed:', e);
      toaster.create({ title: 'Kunde inte aktivera notifikationer', type: 'error', duration: 3000 });
    } finally {
      setLoading(false);
    }
  };

  const unsubscribe = async () => {
    setLoading(true);
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      
      if (sub) {
        await sub.unsubscribe();
        await fetch(`/v1/push/unsubscribe?endpoint=${encodeURIComponent(sub.endpoint)}`, {
          method: 'DELETE',
          credentials: 'include',
        });
      }
      
      setSubscribed(false);
      toaster.create({ title: 'Notifikationer avaktiverade', type: 'info', duration: 2000 });
    } catch (e) {
      console.error('Unsubscribe failed:', e);
    } finally {
      setLoading(false);
    }
  };

  if (!supported) {
    // Check if iOS in browser (not PWA)
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches;
    
    if (isIOS && !isStandalone) {
      return (
        <Box p="12px" bg="blue.900/20" borderRadius="6px" borderWidth="1px" borderColor="blue.500">
          <Text fontSize="sm" fontWeight="medium" color="blue.400" mb="4px">📱 Aktivera notiser på iPhone</Text>
          <Text fontSize="xs" color="fg.muted">
            1. Tryck på dela-knappen (□↑) i Safari{'\n'}
            2. Välj "Lägg till på hemskärmen"{'\n'}
            3. Öppna appen från hemskärmen{'\n'}
            4. Aktivera notiser här
          </Text>
        </Box>
      );
    }
    
    return (
      <Box p="8px" bg="bg.subtle" borderRadius="6px">
        <Text fontSize="sm" color="fg.muted">
          🔕 Push-notiser stöds inte i denna webbläsare
        </Text>
      </Box>
    );
  }

  return (
    <HStack justify="space-between" p="8px" bg="bg.subtle" borderRadius="6px">
      <Box>
        <Text fontSize="sm">🔔 Push-notifikationer</Text>
        <Text fontSize="xs" color="fg.muted">
          {subscribed ? 'Aktiverade' : permission === 'denied' ? 'Blockerade i webbläsaren' : 'Få påminnelser om ombalansering'}
        </Text>
      </Box>
      <Button
        size="xs"
        colorPalette={subscribed ? 'gray' : 'blue'}
        variant={subscribed ? 'outline' : 'solid'}
        onClick={subscribed ? unsubscribe : subscribe}
        loading={loading}
        disabled={permission === 'denied'}
      >
        {subscribed ? 'Avaktivera' : 'Aktivera'}
      </Button>
    </HStack>
  );
}
