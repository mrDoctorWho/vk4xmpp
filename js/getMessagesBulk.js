var users = Args.users.split(",");
var startMessageId = Args.start_message_id;
if (startMessageId == null) {
    startMessageId = 0;
}
var history = [];
var length = users.length;
while (length > 0) {
    var uid = users[length - 1];
    var userHistory = API.messages.getHistory({"user_id": uid, "start_message_id": startMessageId});
    history.push(userHistory);
    length = length - 1;
}
return history;