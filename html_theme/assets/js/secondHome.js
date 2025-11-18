const tabs = document.querySelectorAll("[data-tab-target]");
const tabContents = document.querySelectorAll("[data-tab-content]");


tabs.forEach(tab => {
  tab.addEventListener("click", () => {
    const target = document.querySelector(tab.dataset.tabTarget);
    console.log(target)
    

    tabContents.forEach(tabContent => {
      tabContent.classList.add("hidden");
    })

    tabs.forEach(tab => {
      tab.classList.remove("activeTab");
    })

    tab.classList.add("activeTab");
    target.classList.remove("hidden");
  })
})


function openCollege(event, collegeName){
    let i, tabcontent, tablinks;
  
    tabcontent = document.getElementsByClassName("collegeContent");
    for (i = 0; i < tabcontent.length; i++) {
      tabcontent[i].style.display = "none";
    }
  
    tablinks = document.getElementsByClassName("collegeTab");
    for (i = 0; i < tablinks.length; i++) {
      tablinks[i].classList.remove("activeTab")
    }
  
    document.getElementById(collegeName).style.display = "block";
    event.currentTarget.className += " activeTab";
}

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