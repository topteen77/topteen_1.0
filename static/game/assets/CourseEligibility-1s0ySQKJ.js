import{r as p,j as e,E as $,t as N,s as K,h as H,m as V,g as J}from"./index-CqPkZVHb.js";import{s as Q,a as X}from"./firebase-Cuyihyr5.js";const S={to:"developer.topteen@gmail.com",from:"noreply@testprepgpt.ai"},U=async(n,o,l,t,r="")=>{if(!n)return{success:!1,message:"Recipient email address is required"};if(!o)return{success:!1,message:"Sender email address is required"};if(!l)return{success:!1,message:"Email subject is required"};if(!t&&!r)return{success:!1,message:"Email body (text or HTML) is required"};try{console.log("=== SENDING EMAIL VIA FIREBASE FUNCTION ==="),console.log("To:",n),console.log("From:",o),console.log("Subject:",l),console.log("=== END EMAIL DATA ===");const a=await Q({to:n,from:o,subject:l,text:t,html:r||t});return{success:a.success||!0,message:a.message||"Email sent successfully",messageId:a.messageId||`firebase-${Date.now()}`}}catch(a){return console.error("Error sending email:",a),console.log("=== EMAIL DATA (Error occurred) ==="),console.log("To:",n),console.log("From:",o),console.log("Subject:",l),console.log("=== END EMAIL DATA ==="),{success:!1,message:a.message||"Failed to send email via Firebase Function",error:a}}},Z=n=>{const{phoneNumber:o,careerCluster:l,selectedStreams:t,winnerStream:r,educationInfo:a,course:g}=n,c=`
COURSE APPLICATION
==================

Phone Number: ${o||"N/A"}

Applied Course: ${g||"N/A"}

Career Information:
- Career Cluster: ${l||"N/A"}
- Selected Streams: ${t&&t.length>0?t.join(", "):"N/A"}
- Winner Stream: ${r||"N/A"}

Education Information:
- Background: ${a?.background||"N/A"}
- Stream: ${a?.stream||"N/A"}
- Specific Area: ${a?.specificArea||"N/A"}
- Study Location: ${a?.studyLocation||"N/A"}

---
Generated on: ${new Date().toLocaleString()}
  `.trim(),m=`
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
    .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }
    .content { background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }
    .section { margin-bottom: 20px; }
    .section-title { font-size: 18px; font-weight: bold; color: #667eea; margin-bottom: 10px; border-bottom: 2px solid #667eea; padding-bottom: 5px; }
    .info-item { margin: 8px 0; }
    .info-label { font-weight: bold; color: #555; }
    .course-highlight { background: white; padding: 15px; border-radius: 5px; margin-top: 10px; border-left: 4px solid #667eea; font-size: 16px; font-weight: bold; color: #667eea; }
    .footer { text-align: center; color: #666; font-size: 12px; margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Course Application</h1>
    </div>
    <div class="content">
      <div class="section">
        <div class="section-title">Contact Information</div>
        <div class="info-item">
          <span class="info-label">Phone Number:</span> ${o||"N/A"}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Applied Course</div>
        <div class="course-highlight">${g||"N/A"}</div>
      </div>

      <div class="section">
        <div class="section-title">Career Information</div>
        <div class="info-item">
          <span class="info-label">Career Cluster:</span> ${l||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Selected Streams:</span> ${t&&t.length>0?t.join(", "):"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Winner Stream:</span> ${r||"N/A"}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Education Information</div>
        <div class="info-item">
          <span class="info-label">Background:</span> ${a?.background||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Stream:</span> ${a?.stream||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Specific Area:</span> ${a?.specificArea||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Study Location:</span> ${a?.studyLocation||"N/A"}
        </div>
      </div>
    </div>
    <div class="footer">
      Generated on: ${new Date().toLocaleString()}
    </div>
  </div>
</body>
</html>
  `.trim();return{textBody:c,htmlBody:m}},ee=n=>{const{phoneNumber:o,careerCluster:l,selectedStreams:t,winnerStream:r,educationInfo:a}=n,g=`
USER DETAILS FOR COUNSELLOR
===========================

Phone Number: ${o||"N/A"}

Career Information:
- Career Cluster: ${l||"N/A"}
- Selected Streams: ${t&&t.length>0?t.join(", "):"N/A"}
- Winner Stream: ${r||"N/A"}

Education Information:
- Background: ${a?.background||"N/A"}
- Stream: ${a?.stream||"N/A"}
- Specific Area: ${a?.specificArea||"N/A"}
- Study Location: ${a?.studyLocation||"N/A"}

---
Generated on: ${new Date().toLocaleString()}
  `.trim(),c=`
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
    .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }
    .content { background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }
    .section { margin-bottom: 20px; }
    .section-title { font-size: 18px; font-weight: bold; color: #667eea; margin-bottom: 10px; border-bottom: 2px solid #667eea; padding-bottom: 5px; }
    .info-item { margin: 8px 0; }
    .info-label { font-weight: bold; color: #555; }
    .footer { text-align: center; color: #666; font-size: 12px; margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>User Details for Counsellor</h1>
    </div>
    <div class="content">
      <div class="section">
        <div class="section-title">Contact Information</div>
        <div class="info-item">
          <span class="info-label">Phone Number:</span> ${o||"N/A"}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Career Information</div>
        <div class="info-item">
          <span class="info-label">Career Cluster:</span> ${l||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Selected Streams:</span> ${t&&t.length>0?t.join(", "):"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Winner Stream:</span> ${r||"N/A"}
        </div>
      </div>

      <div class="section">
        <div class="section-title">Education Information</div>
        <div class="info-item">
          <span class="info-label">Background:</span> ${a?.background||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Stream:</span> ${a?.stream||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Specific Area:</span> ${a?.specificArea||"N/A"}
        </div>
        <div class="info-item">
          <span class="info-label">Study Location:</span> ${a?.studyLocation||"N/A"}
        </div>
      </div>
    </div>
    <div class="footer">
      Generated on: ${new Date().toLocaleString()}
    </div>
  </div>
</body>
</html>
  `.trim();return{textBody:g,htmlBody:c}},se=async n=>{try{const{textBody:o,htmlBody:l}=ee(n),t=`User Eligibility Check - ${n.phoneNumber||"Unknown"}`,r=await U(S.to,S.from,t,o,l);return r.success?console.log("User data email sent successfully (silent)"):console.warn("Failed to send user data email (silent):",r.message),r}catch(o){return console.error("Error sending user data email (silent):",o),{success:!1,message:o.message}}},ae=async n=>{const{textBody:o,htmlBody:l}=Z(n),t=`Course Application - ${n.course||"Unknown Course"} - ${n.phoneNumber||"Unknown"}`;return await U(S.to,S.from,t,o,l)},le=({winnerStream:n,fightResult:o,selectedStreams:l,selectedParameters:t,selectedCluster:r,onBack:a,onReset:g})=>{const[c,m]=p.useState(1),[d,O]=p.useState(null),[u,T]=p.useState(null),[h,F]=p.useState(null),[b,_]=p.useState(null),[y,G]=p.useState(null),[E,I]=p.useState(!1),[w,A]=p.useState(null),[R,L]=p.useState(!1),[j,v]=p.useState(null),M=s=>{const i=localStorage.getItem("userPhoneNumber");i&&N(i,"education_background_selected",{background:s}),O(s),m(2)},z=s=>{const i=localStorage.getItem("userPhoneNumber");i&&N(i,"education_stream_selected",{stream:s,background:d}),T(s),m(3)},Y=s=>{const i=localStorage.getItem("userPhoneNumber");i&&N(i,"specific_area_selected",{area:s,stream:u,background:d}),F(s)},D=s=>{const i=localStorage.getItem("userPhoneNumber");i&&N(i,"study_location_selected",{location:s}),_(s)},q=async()=>{if(!d||!u||!h||!b){A("Please complete all selections");return}const s=localStorage.getItem("userPhoneNumber");s?console.log("User phone number:",s):console.log("No phone number found in storage"),I(!0),A(null);try{const i={background:d,stream:u,specificArea:h,studyLocation:b},x=(await X({educationBackground:{background:d,stream:u,specificArea:h},winnerStream:n})).courses||[];G(x),s&&(K(s,{educationInfo:i,courses:x,winnerStream:n,fightResult:o,selectedStreams:l,selectedParameters:t,selectedCluster:r}),N(s,"eligibility_checked",{courses:x,educationInfo:i}),H(s)?console.log("Eligibility email already sent, skipping duplicate"):se({phoneNumber:s,careerCluster:r||null,selectedStreams:l||[],winnerStream:n||null,educationInfo:i}).then(C=>{C.success&&(V(s),console.log("Eligibility email sent and marked as sent"))}).catch(C=>{console.error("Silent email error:",C)})),m(5)}catch(i){console.error("Error checking course eligibility:",i),A(i.message||"Failed to check course eligibility. Please try again.")}finally{I(!1)}},B=d&&u&&h&&b,W=async s=>{const i=localStorage.getItem("userPhoneNumber");if(!i){alert("No user data found. Please login first.");return}v(s);try{const f=J(i),x={phoneNumber:i,careerCluster:r||null,selectedStreams:l||[],winnerStream:n||null,educationInfo:f.educationInfo||null,course:s},k=await ae(x);k.success?(L(!0),N(i,"course_application",{course:s})):(alert(`Failed to send application: ${k.message}`),v(null))}catch(f){console.error("Error sending course application:",f),alert(`Error sending application: ${f.message}`),v(null)}},P=()=>{L(!1),v(null),g?g():a&&a(),window.location.reload()};return e.jsxs("div",{className:"course-eligibility-container",role:"region","aria-labelledby":"course-eligibility-title",children:[e.jsxs("div",{className:"course-eligibility-header",children:[e.jsx("h1",{id:"course-eligibility-title",className:"course-eligibility-title",children:"Course Eligibility Check"}),e.jsxs("p",{className:"course-eligibility-subtitle",children:["Based on your education background and the winner stream: ",e.jsx("strong",{children:n})]})]}),c<5&&e.jsxs("div",{className:"step-indicator",children:[e.jsxs("div",{className:`step ${c>=1?"step-active":""}`,children:[e.jsx("span",{className:"step-number",children:"1"}),e.jsx("span",{className:"step-label",children:"Education"})]}),e.jsx("div",{className:`step-connector ${c>=2?"connector-active":""}`}),e.jsxs("div",{className:`step ${c>=2?"step-active":""}`,children:[e.jsx("span",{className:"step-number",children:"2"}),e.jsx("span",{className:"step-label",children:"Stream"})]}),e.jsx("div",{className:`step-connector ${c>=3?"connector-active":""}`}),e.jsxs("div",{className:`step ${c>=3?"step-active":""}`,children:[e.jsx("span",{className:"step-number",children:"3"}),e.jsx("span",{className:"step-label",children:"Area"})]}),e.jsx("div",{className:`step-connector ${c>=4?"connector-active":""}`}),e.jsxs("div",{className:`step ${c>=4?"step-active":""}`,children:[e.jsx("span",{className:"step-number",children:"4"}),e.jsx("span",{className:"step-label",children:"Location"})]})]}),c===1&&e.jsxs("div",{className:"eligibility-step",children:[e.jsx("h2",{className:"step-title",children:"Select Your Education Background"}),e.jsx("div",{className:"options-grid",children:Object.keys($).map(s=>e.jsx("button",{className:`option-card ${d===s?"option-card-selected":""}`,onClick:()=>M(s),"aria-pressed":d===s,children:e.jsx("span",{className:"option-name",children:s})},s))})]}),c===2&&d&&e.jsxs("div",{className:"eligibility-step",children:[e.jsx("h2",{className:"step-title",children:"Select Your Stream"}),e.jsx("div",{className:"options-grid",children:$[d].streams.map(s=>e.jsx("button",{className:`option-card ${u===s?"option-card-selected":""}`,onClick:()=>z(s),"aria-pressed":u===s,children:e.jsx("span",{className:"option-name",children:s})},s))}),e.jsx("button",{className:"back-button",onClick:()=>m(1),children:"← Back"})]}),c===3&&d&&u&&e.jsxs("div",{className:"eligibility-step",children:[e.jsx("h2",{className:"step-title",children:"Select Specific Area"}),e.jsx("div",{className:"options-grid",children:$[d].specificAreas[u].map(s=>e.jsx("button",{className:`option-card ${h===s?"option-card-selected":""}`,onClick:()=>Y(s),"aria-pressed":h===s,children:e.jsx("span",{className:"option-name",children:s})},s))}),e.jsxs("div",{className:"step-actions",children:[e.jsx("button",{className:"back-button",onClick:()=>m(2),children:"← Back"}),h&&e.jsx("button",{className:"continue-button",onClick:()=>m(4),children:"Continue →"})]})]}),c===4&&d&&u&&h&&e.jsxs("div",{className:"eligibility-step",children:[e.jsx("h2",{className:"step-title",children:"Select Study Location"}),e.jsxs("div",{className:"options-grid",children:[e.jsx("button",{className:`option-card ${b==="India"?"option-card-selected":""}`,onClick:()=>D("India"),"aria-pressed":b==="India",children:e.jsx("span",{className:"option-name",children:"🇮🇳 India"})}),e.jsx("button",{className:`option-card ${b==="Study Abroad"?"option-card-selected":""}`,onClick:()=>D("Study Abroad"),"aria-pressed":b==="Study Abroad",children:e.jsx("span",{className:"option-name",children:"🌍 Study Abroad"})})]}),e.jsxs("div",{className:"step-actions",children:[e.jsx("button",{className:"back-button",onClick:()=>m(3),children:"← Back"}),e.jsx("button",{className:`check-button ${B?"check-button-active":"check-button-disabled"}`,onClick:q,disabled:!B||E,children:E?"Checking...":"Check Eligibility"})]})]}),w&&e.jsx("div",{className:"error-message",role:"alert",children:w}),c===5&&y&&e.jsxs("div",{className:"courses-results",children:[e.jsx("h2",{className:"results-title",children:"Eligible Courses"}),e.jsx("div",{className:"courses-list",children:y.length>0?e.jsx("ul",{className:"courses-ul",children:y.map((s,i)=>e.jsxs("li",{className:"course-item",children:[e.jsx("span",{className:"course-icon",children:"📚"}),e.jsx("span",{className:"course-name",children:s}),e.jsx("button",{className:"apply-button",onClick:()=>W(s),disabled:j===s,children:j===s?"Sending...":"Apply"})]},i))}):e.jsx("p",{className:"no-courses",children:"No eligible courses found."})}),e.jsx("div",{className:"results-actions",children:e.jsx("button",{className:"back-button",onClick:a,children:"← Back to Game"})})]}),R&&e.jsx("div",{className:"success-popup-overlay",onClick:P,children:e.jsxs("div",{className:"success-popup",onClick:s=>s.stopPropagation(),children:[e.jsx("div",{className:"success-popup-icon",children:"✅"}),e.jsx("h2",{className:"success-popup-title",children:"Thank You!"}),e.jsx("p",{className:"success-popup-message",children:"Our counsellor will contact you soon regarding your application for:"}),e.jsx("p",{className:"success-popup-course",children:j}),e.jsx("button",{className:"success-popup-button",onClick:P,children:"OK"})]})})]})};export{le as default};
