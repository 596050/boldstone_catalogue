-- Chrome's public scripting dictionary, against the existing normal instance.
-- No System Events, accessibility input, clipboard, activate, or new tabs/windows.
use framework "Foundation"
use framework "AppKit"
use scripting additions

on jsonText(anObject)
    set encodedData to current application's NSJSONSerialization's dataWithJSONObject:anObject options:0 |error|:(missing value)
    if encodedData is missing value then error "JSON_ENCODING_FAILED"
    return (current application's NSString's alloc()'s initWithData:encodedData encoding:(current application's NSUTF8StringEncoding)) as text
end jsonText

on foregroundBundle()
    set frontApplication to current application's NSWorkspace's sharedWorkspace()'s frontmostApplication()
    return (frontApplication's bundleIdentifier()) as text
end foregroundBundle

on jsonObject(keyList, valueList)
    set resultDictionary to current application's NSMutableDictionary's dictionary()
    repeat with itemNumber from 1 to count of keyList
        resultDictionary's setObject:(item itemNumber of valueList) forKey:(item itemNumber of keyList)
    end repeat
    return resultDictionary
end jsonObject

on inventory()
    set frontBundle to my foregroundBundle()
    if application id "com.google.Chrome" is not running then
        return my jsonText(my jsonObject({"chrome_running", "frontmost", "windows"}, {false, frontBundle, current application's NSArray's array()}))
    end if
    set windowRows to current application's NSMutableArray's array()
    tell application "Google Chrome"
        set chromeVersion to version
        set windowIDs to id of every window
        repeat with windowID in windowIDs
            set browserWindow to window id (windowID as integer)
            set tabRows to current application's NSMutableArray's array()
            set tabIDs to id of every tab of browserWindow
            repeat with tabID in tabIDs
                set browserTab to tab id (tabID as integer) of browserWindow
                set tabRow to my jsonObject({"tab_id", "url", "title", "loading"}, {(id of browserTab), (URL of browserTab), (title of browserTab), (loading of browserTab)})
                tabRows's addObject:tabRow
            end repeat
            set windowRow to my jsonObject({"window_id", "active_tab_id", "mode", "tabs"}, {(id of browserWindow), (id of active tab of browserWindow), (mode of browserWindow), tabRows})
            windowRows's addObject:windowRow
        end repeat
    end tell
    return my jsonText(my jsonObject({"chrome_running", "chrome_version", "frontmost", "windows"}, {true, chromeVersion, frontBundle, windowRows}))
end inventory

on tabState(wantedWindow, wantedTab)
    set frontBundle to my foregroundBundle()
    if application id "com.google.Chrome" is not running then error "CHROME_NOT_RUNNING"
    set windowRows to current application's NSMutableArray's array()
    tell application "Google Chrome"
        set windowIDs to id of every window
        repeat with windowID in windowIDs
            set browserWindow to window id (windowID as integer)
            set tabRows to current application's NSMutableArray's array()
            if ((id of browserWindow) as integer) is wantedWindow then
                set browserTab to tab id wantedTab of browserWindow
                tabRows's addObject:(my jsonObject({"tab_id", "url", "loading"}, {(id of browserTab), (URL of browserTab), (loading of browserTab)}))
            end if
            windowRows's addObject:(my jsonObject({"window_id", "active_tab_id", "mode", "tabs"}, {(id of browserWindow), (id of active tab of browserWindow), (mode of browserWindow), tabRows}))
        end repeat
    end tell
    return my jsonText(my jsonObject({"chrome_running", "frontmost", "windows"}, {true, frontBundle, windowRows}))
end tabState

on run argv
    if (count of argv) is 0 then error "Expected inventory, tab-state, inspect or execute"
    set operationName to item 1 of argv
    with timeout of 5 seconds
        if operationName is "inventory" then return my inventory()
        if operationName is "tab-state" then
            if (count of argv) is not 3 then error "Expected tab-state, window ID and tab ID"
            return my tabState((item 2 of argv) as integer, (item 3 of argv) as integer)
        end if
        if (count of argv) is not 5 then error "Expected operation, window ID, tab ID, expected URL and payload path/URL"
        if application id "com.google.Chrome" is not running then error "CHROME_NOT_RUNNING"
        set wantedWindow to (item 2 of argv) as integer
        set wantedTab to (item 3 of argv) as integer
        set expectedURL to item 4 of argv
        set payloadArgument to item 5 of argv
        set frontBundle to my foregroundBundle()
        tell application "Google Chrome"
            set selectedWindow to window id wantedWindow
            if mode of selectedWindow is not "normal" then error "NORMAL_PROFILE_REQUIRED"
            set selectedTab to tab id wantedTab of selectedWindow
            if URL of selectedTab is not expectedURL then error "TAB_NAVIGATED_EXTERNALLY"
            if operationName is not "inspect" then
                if frontBundle is "com.google.Chrome" and ((id of front window) as integer) is wantedWindow and ((id of active tab of selectedWindow) as integer) is wantedTab then error "FOREGROUND_TAB_PAUSED"
            end if
            if operationName is not "inspect" and operationName is not "execute" then error "UNSUPPORTED_OPERATION"
            set javascriptText to read (POSIX file payloadArgument) as «class utf8»
            return execute selectedTab javascript javascriptText
        end tell
    end timeout
end run

