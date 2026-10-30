$(document).ready(function(){

  $("#save-btn").click(function(){

   
   var id = $("#id").val();
   var pw = $("#pw").val();
   var pwCheck = $("#pw-check").val();
   var nick = $("#nick").val();
   var addr = $("#addr").val();
   var type = $("#type-slt").val();

   if(id == ""){
    alert("아이디를 입력해주세요");
    return;
   }

   if(pw == ""){
    alert("비밀번호를 입력해주세요");
    return;
   }

   if(nick == ""){
    alert("닉네임을 입력해주세요");
    return;
   }

   if(addr == ""){
    alert("주소를 입력해주세요");
    return;
   }

   if(pw != pwCheck){
    alert("비밀번호가 일치하지 않습니다");
    return;
   }


   $.ajax({
      url:"./api/user/add-user",
      type:"post",
      contentType:"application/json",
      data:JSON.stringify({
         'id':id,
         'pw':pw,
         'nick':nick,
         'type':type,
         'addr':addr
      }),
      success:function(response){
         if(response.message == "ok"){
            alert("회원가입 완료");
            location.href = "./";
         }else{
            alert("회원가입 실패");
         }
      },
      error:function(error){
         console.log(error);
      }
   });



  });

  
});
