//
//  Copyright © 2018 Simon Kågedal Reimer. All rights reserved.
//

import UIKit
import WebKit

class WKWebViewViewController: UIViewController, WKNavigationDelegate {

    @IBOutlet private var webView: WKWebView!
    @IBOutlet private var label: UILabel!
    
    override func viewDidLoad() {
        super.viewDidLoad()

        webView.navigationDelegate = self
        webView.load(.testPOSTInterception)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        
        let request = navigationAction.request
        if request.httpMethod == "POST" {
            label.text = request.interceptedPostDataDescription
            decisionHandler(.cancel)
        } else {
            decisionHandler(.allow)
        }

    }
}
