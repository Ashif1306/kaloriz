(function () {
  const cards = document.querySelectorAll('[data-end-time]');
  if (!cards.length) return;

  function formatTime(diffMs) {
    const totalSeconds = Math.max(0, Math.floor(diffMs / 1000));
    const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, '0');
    const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0');
    const seconds = String(totalSeconds % 60).padStart(2, '0');
    return `${hours}:${minutes}:${seconds}`;
  }

  cards.forEach((card) => {
    const endIso = card.dataset.endTime;
    if (!endIso) return;

    const endTime = new Date(endIso);
    const countdownWrapper = card.querySelector('[data-countdown]');
    const countdownText = countdownWrapper ? countdownWrapper.querySelector('span') || countdownWrapper : null;
    const buyButton = card.querySelector('.btn-beli-sekarang');

    function updateCountdown() {
      const now = new Date();
      const diff = endTime - now;

      if (!countdownWrapper || !countdownText) {
        return;
      }

      if (isNaN(diff)) {
        countdownText.textContent = 'Tidak valid';
        return;
      }

      if (diff <= 0) {
        countdownText.textContent = 'Flash Sale Berakhir';
        countdownWrapper.classList.add('text-muted');
        card.classList.add('flash-ended');
        if (buyButton) {
          buyButton.setAttribute('disabled', 'disabled');
          buyButton.title = 'Flash sale sudah berakhir';
        }
        clearInterval(intervalId);
        return;
      }

      countdownText.textContent = formatTime(diff);
    }

    updateCountdown();
    const intervalId = setInterval(updateCountdown, 1000);
  });
})();
