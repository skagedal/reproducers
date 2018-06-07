//
//  Copyright © 2018 Simon Kågedal Reimer. All rights reserved.
//

import UIKit

class UIWebViewViewController: UIViewController, UIWebViewDelegate {
    
    @IBOutlet private var webView: UIWebView!
    @IBOutlet private var label: UILabel!
    
    override func viewDidLoad() {
        super.viewDidLoad()

        webView.loadRequest(.testPOSTInterception)
    }

    func webView(_ webView: UIWebView, shouldStartLoadWith request: URLRequest, navigationType: UIWebViewNavigationType) -> Bool {
        
        if request.httpMethod == "POST" {
            label.text = request.interceptedPostDataDescription
            return false
        }
        return true
    }
}
