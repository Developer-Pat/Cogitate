import { useNotificationStore } from '../stores/notificationStore'

export function useNotifications() {
  const { addNotification, removeNotification, clearNotifications } = useNotificationStore()

  const notifySuccess = (title: string, message: string, duration?: number) => {
    addNotification({
      type: 'success',
      title,
      message,
      duration
    })
  }

  const notifyError = (title: string, message: string, duration?: number) => {
    addNotification({
      type: 'error',
      title,
      message,
      duration
    })
  }

  const notifyWarning = (title: string, message: string, duration?: number) => {
    addNotification({
      type: 'warning',
      title,
      message,
      duration
    })
  }

  const notifyInfo = (title: string, message: string, duration?: number) => {
    addNotification({
      type: 'info',
      title,
      message,
      duration
    })
  }

  return {
    notifySuccess,
    notifyError,
    notifyWarning,
    notifyInfo,
    removeNotification,
    clearNotifications
  }
}