var dialogs = API.messages.searchDialogs({"limit":200});
var len = dialogs.length;
var chats = [];
while (len >= 0) {
    var dialog = dialogs[len];
    if (dialog.type) {
        if (dialog.type == "chat") {
            chats.push(dialog);
        }
    }
    len = len - 1;
}
return chats; 
