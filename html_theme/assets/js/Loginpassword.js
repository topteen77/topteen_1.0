const popup = document.getElementById("popup");
const open = document.getElementById("open");
const closeBtn = document.querySelector("#closePopup");
console.log(open);
function showpage(value) {
  if (value) {
    popup?.classList.remove("hidden");
    open?.classList.add("hidden");
  } else {
    setTimeout(() => {
      popup?.classList.add("hidden");
    }, 100);
    open?.classList.remove("hidden");
  }
}

open?.addEventListener("click", function (e) {
  e.preventDefault();

  showpage(true);
});

closeBtn?.addEventListener("click", function (e) {
  e.preventDefault();
  showpage(false);
});

// BUTTON CONTINUE => OPEN ID

// 123456
const otpSource = document.querySelector(".otpSource");


const otpIp = document.querySelectorAll(".otpIp");

function changeHandler(){
  const otpData = otpSource.value;
  console.log(otpData.length)
  if(otpData.length == 6){
    for(i=0; i<otpData.length; i++){
      otpIp[i].value = otpData[i]
    }  
  } else if(otpData.length == 1){
    console.log("typed")
  }
}


otpSource.addEventListener("input", changeHandler)





