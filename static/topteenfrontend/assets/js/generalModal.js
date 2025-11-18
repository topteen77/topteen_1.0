const modalTriggerAll = document.querySelectorAll(".modalTrigger");

[...modalTriggerAll]?.forEach((trigger) => {
  const target = trigger.dataset.target;
  const hiddenClass = trigger.dataset.hiddenclass || "hidden";
  if (!target) return;
  const targetModal = document.querySelector(`${target}`);
  // const modalCloser = targetModal?.querySelector(".modalCloser");

  const closeModal = function () {
    if (targetModal) {
      targetModal.classList.add(hiddenClass);
    }
  };

  if (targetModal) {
    targetModal?.addEventListener("click", function (e) {
      const parentTarget = e.target.closest(".modalContent");
      if (parentTarget) {
        const closer = e.target.closest(".modalCloser");
        if (closer) {
          closeModal();
        } else {
          return;
        }
      } else {
        closeModal();
      }
    });
  }

  trigger.addEventListener("click", function () {
    if (targetModal) {
      targetModal.classList.remove(hiddenClass);
    }
  });
});
