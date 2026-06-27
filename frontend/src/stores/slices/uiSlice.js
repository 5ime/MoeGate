export function createUiSlice() {
  return {
    activeTab: 'containers',
    message: '',
    messageType: 'success',
    detailPanel: {
      open: false,
      title: '',
      payload: null,
    },
  };
}

export function resetUiSlice(store) {
  store.message = '';
  store.messageType = 'success';
  store.detailPanel.open = false;
  store.detailPanel.title = '';
  store.detailPanel.payload = null;
}
