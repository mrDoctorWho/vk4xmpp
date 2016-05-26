// Makes no sense just like getLastTime
// Used to prevent getting wrong answer from VK API
// They usually block or don't answer for usual queries
// But they always offer to use execute. So, why not?
var data = API.users.get();
return data[0].uid; 
