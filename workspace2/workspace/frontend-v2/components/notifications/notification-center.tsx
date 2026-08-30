"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { useUIStore } from "../../store/ui-store";
export function NotificationCenter() { const { notificationsOpen, setNotificationsOpen } = useUIStore(); return <Dialog.Root open={notificationsOpen} onOpenChange={setNotificationsOpen}><Dialog.Portal><Dialog.Overlay className="dialog-overlay"/><Dialog.Content className="notification-center"><Dialog.Title>Notifications</Dialog.Title><p>No notifications have been received from the connected backend.</p><button onClick={() => setNotificationsOpen(false)}>Close</button></Dialog.Content></Dialog.Portal></Dialog.Root>; }
