export const getSpaceKeyFromURL = (): string | null => {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('space');
};

export const isSpaceConnected = (): boolean => {
  return getSpaceKeyFromURL() !== null;
}; 