#include <iostream>
using namespace std;

int main() {
    int n, sum = 0;
    cin >> n;
    for (int i = 1; i <= n; i++) {
        sum += i;
    }
    if (sum > 100) {
        cout << "big: " << sum << endl;
    } else {
        cout << "small: " << sum << endl;
    }
    int k = 0;
    do {
        k++;
    } while (k < 3);
    while (k > 0) {
        k--;
        if (k == 2) continue;
    }
    switch (k) {
        case 0: cout << "zero" << endl; break;
        case 1: cout << "one" << endl; break;
        default: cout << "other" << endl;
    }
    return 0;
}
