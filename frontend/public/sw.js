// Service Worker for Aula PWA - handles push notifications

self.addEventListener("push", (event) => {
  const data = event.data?.json() ?? { title: "Aula", body: "Ny besked" };
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/icon-192.png",
      badge: "/icon-192.png",
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow("/dashboard"));
});
