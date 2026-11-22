-- Compact, target-scoped audit for Google preparation; never used for Post.
use framework "Foundation"
use framework "AppKit"
use scripting additions

on jsonObject(keyList, valueList)
    set resultDictionary to current application's NSMutableDictionary's dictionary()
    repeat with itemNumber from 1 to count of keyList
        resultDictionary's setObject:(item itemNumber of valueList) forKey:(item itemNumber of keyList)
    end repeat
    return resultDictionary
end jsonObject

on jsonText(anObject)
    set encodedData to current application's NSJSONSerialization's dataWithJSONObject:anObject options:0 |error|:(missing value)
    if encodedData is missing value then error "JSON_ENCODING_FAILED"
    return (current application's NSString's alloc()'s initWithData:encodedData encoding:(current application's NSUTF8StringEncoding)) as text
end jsonText

on targetStamp(wantedWindow, wantedTab, windowKey)
    set frontApplication to current application's NSWorkspace's sharedWorkspace()'s frontmostApplication()
    set frontBundle to (frontApplication's bundleIdentifier()) as text
    if application id "com.google.Chrome" is not running then error "CHROME_NOT_RUNNING"
    tell application "Google Chrome"
        set selectedWindow to window id wantedWindow
        if mode of selectedWindow is not "normal" then error "NORMAL_PROFILE_REQUIRED"
        set selectedTab to tab id wantedTab of selectedWindow
        set frontID to id of front window
        set activeID to id of active tab of selectedWindow
        set tabURL to URL of selectedTab
    end tell
    set activeTabs to my jsonObject({windowKey}, {activeID})
    return my jsonObject({"frontmost", "front_window_id", "active_tabs", "tab_url"}, {frontBundle, frontID, activeTabs, tabURL})
end targetStamp

on run argv
    if (count of argv) is not 4 then error "Expected window ID, tab ID, expected URL and payload path"
    set wantedWindow to (item 1 of argv) as integer
    set windowKey to item 1 of argv
    set wantedTab to (item 2 of argv) as integer
    set expectedURL to item 3 of argv
    set payloadArgument to item 4 of argv
    with timeout of 5 seconds
        set beforeStamp to my targetStamp(wantedWindow, wantedTab, windowKey)
        if (beforeStamp's objectForKey:"tab_url") as text is not expectedURL then error "TAB_NAVIGATED_EXTERNALLY"
        if ((beforeStamp's objectForKey:"frontmost") as text) is "com.google.Chrome" and ((beforeStamp's objectForKey:"front_window_id") as integer) is wantedWindow then
            set activeTabs to beforeStamp's objectForKey:"active_tabs"
            if ((activeTabs's objectForKey:windowKey) as integer) is wantedTab then error "FOREGROUND_TAB_PAUSED"
        end if
        set javascriptString to current application's NSString's stringWithContentsOfFile:payloadArgument encoding:(current application's NSUTF8StringEncoding) |error|:(missing value)
        if javascriptString is missing value then error "PAYLOAD_UNAVAILABLE"
        set javascriptText to javascriptString as text
        tell application "Google Chrome"
            set selectedTab to tab id wantedTab of window id wantedWindow
            set domResult to execute selectedTab javascript javascriptText
        end tell
        set afterStamp to my targetStamp(wantedWindow, wantedTab, windowKey)
        return my jsonText(my jsonObject({"result_json", "before", "after"}, {domResult, beforeStamp, afterStamp}))
    end timeout
end run
