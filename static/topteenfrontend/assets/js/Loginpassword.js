const popup = document.getElementById("popup");
const open = document.getElementById("open");
function showpage(value) {
  if (value) {
    popup.classList.remove("hidden");
    open.classList.add("hidden");
  } else {
    setTimeout(() => {
      popup.classList.add("hidden");
    }, 100);
    open.classList.remove("hidden");
  }
}


