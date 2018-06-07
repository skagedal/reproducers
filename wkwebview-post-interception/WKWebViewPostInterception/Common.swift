//
//  Copyright © 2018 Simon Kågedal Reimer. All rights reserved.
//

import UIKit

extension URLRequest {
    static var testPOSTInterception: URLRequest {
        let url = URL(string: "https://skagedal.github.io/radars/wkwebview")!
        return URLRequest(url: url)
    }

    var interceptedPostDataDescription: String {
        if let data = httpBody {
            if let string = String(data: data, encoding: .utf8) {
                return "Intercepted POST data:\n\(string)"
            } else {
                return "Intercepted POST data, \(data.count) bytes"
            }
        } else {
            return "Intercepted POST, but got no data"
        }
    }
}

