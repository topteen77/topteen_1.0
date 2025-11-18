const colors = ['FBCACA', 'F9F4BB', 'DEF7BB', 'B9F4EC', 'C3B9F4', 'E7B9F4', 'F4B9E1', 'F3B8C2']
randomBgColor();


// Career Choices
const openCareer = function(event, careerName){
  console.log("hello")
  let tabcontent, tablinks;

  tabcontent = document.querySelectorAll(".careerContent");
  tabcontent.forEach(content => {
    content.style.display = "none";
  })

  tablinks = document.querySelectorAll(".careerTab");
  tablinks.forEach(tab => {
    tab.classList.remove("activeTab");
  })

  document.getElementById(careerName).style.display = "flex";
  event.currentTarget.className += " activeTab";
}

// College Recommendations
function openCollege(event, collegeName){
    let tabcontent, tablinks;
  
    tabcontent = document.querySelectorAll(".collegeContent");
    tabcontent.forEach(content => {
      content.style.display = "none";
    })
  
    tablinks = document.querySelectorAll(".collegeTab");
    tablinks.forEach(tab => {
      tab.classList.remove("activeTab");
    })
  
    document.getElementById(collegeName).style.display = "block";
    event.currentTarget.className += " activeTab";
}

// Important Exams
function openExams(event, examName){
    let i, tabcontent, tablinks;
  
    tabcontent = document.getElementsByClassName("examContent");
    for (i = 0; i < tabcontent.length; i++) {
      tabcontent[i].style.display = "none";
    }
  
    tablinks = document.getElementsByClassName("examsTab");
    for (i = 0; i < tablinks.length; i++) {
      tablinks[i].classList.remove("activeTab")
    }
  
    document.getElementById(examName).style.display = "block";
    event.currentTarget.className += " activeTab";
}

// Add Folder PopUp
const addFolderPop = document.querySelector(".addFolderPop");
const addFolderPopBtn = document.querySelector(".addFolderPopBtn");
const addFolderCloseBtn = document.querySelector(".addFolderCloseBtn");
const folderSaveBtn = document.querySelector(".folderSaveBtn");

if(addFolderPopBtn){
    addFolderPopBtn.addEventListener("click", function(){
      addFolderPop.classList.remove("hidden");
    })
      
    addFolderCloseBtn.addEventListener("click", function(){
      addFolderPop.classList.add("hidden");
    })

    folderSaveBtn.addEventListener('click', function(e){
      e.preventDefault();
      addFolderPop.classList.add("hidden");
   })

}


// Random background Color

function randomBgColor(){
  const addedFolders = document.querySelectorAll(".addedFolder");
  
  addedFolders.forEach(elem => {
    const selectedColor = getRandomBg();
    elem.style.backgroundColor = selectedColor;
  })
  
}



function getRandomBg(){
  let randomBg = '#'+colors[Math.floor(Math.random()*colors.length)];
  return randomBg;
}