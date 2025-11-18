let beforeType = document.querySelector(".beforeType");
let beforeTypeOne = document.getElementById("beforeTypeOne");
let afterType = document.querySelector(".afterType");
let nothingFound = document.querySelector(".nothingFound");
let mainPart = document.querySelector(".mainPart");
let searchBox = document.querySelector(".searchBox")
let searchBoxOne = document.querySelector(".searchBoxOne");

const focusFunc = () => {
    beforeType.classList.remove("hidden");
    // mainPart.classList.add("opacity-30")
}


searchBoxOne.addEventListener("focus", function(){

    beforeTypeOne.classList.remove("hidden");
    // mainPart.classList.remove("opacity-30")
})

searchBox.addEventListener("focusout", function(){
    beforeType.classList.add("hidden");
    // mainPart.classList.remove("opacity-30")
})

document.onclick = function(e){
    // if( e.target.classList !== "beforeType"){
    //     beforeType.classList.add("hidden");
    //     afterType.classList.add("hidden");
    // }
}

const inputFunc = () => {
    beforeType?.classList.add("hidden");
    afterType.classList.remove("hidden");
    
}


