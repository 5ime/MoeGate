export function createAuthSlice() {
  return {
    sessionAuthenticated: false,
  };
}

export function resetAuthSlice(store) {
  store.sessionAuthenticated = false;
}
