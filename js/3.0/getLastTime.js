// It makes no sense and not required at all
// Allows to get user's last activity

var uid = Args.uid;
var time = API.messages.getLastActivity({"user_id": uid});
return time.time; 
