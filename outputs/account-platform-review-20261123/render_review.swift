import Cocoa
import WebKit

final class Renderer: NSObject, WKNavigationDelegate {
    let web: WKWebView
    let destination: URL
    var finished = false
    var succeeded = false
    init(_ web: WKWebView, _ destination: URL) { self.web=web; self.destination=destination }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        webView.evaluateJavaScript("document.documentElement.scrollHeight") { value,error in
            guard error == nil, let height = value as? Double else { self.finished=true; return }
            let config=WKSnapshotConfiguration()
            config.rect=CGRect(x:0,y:0,width:1280,height:min(8500,height))
            config.snapshotWidth=1280
            config.afterScreenUpdates=true
            webView.setFrameSize(CGSize(width:1280,height:min(8500,height)))
            webView.takeSnapshot(with:config) { image,error in
                if let image=image, let tiff=image.tiffRepresentation,
                   let bitmap=NSBitmapImageRep(data:tiff), let png=bitmap.representation(using:.png,properties:[:]) {
                    do { try png.write(to:self.destination); self.succeeded=true } catch { print(error) }
                } else if let error=error { print(error) }
                self.finished=true
            }
        }
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { print(error); finished=true }
}
let app=NSApplication.shared
app.setActivationPolicy(.prohibited)
let input=URL(fileURLWithPath:CommandLine.arguments[1])
let output=URL(fileURLWithPath:CommandLine.arguments[2])
let web=WKWebView(frame:CGRect(x:0,y:0,width:1280,height:900))
let window=NSWindow(contentRect:web.frame,styleMask:.borderless,backing:.buffered,defer:false)
window.contentView=web
let renderer=Renderer(web,output)
web.navigationDelegate=renderer
web.loadFileURL(input,allowingReadAccessTo:input.deletingLastPathComponent())
let deadline=Date().addingTimeInterval(35)
while !renderer.finished && Date()<deadline { RunLoop.main.run(until:Date().addingTimeInterval(0.1)) }
if !renderer.succeeded { print("Offscreen render unavailable"); exit(2) }
print(output.path)
