#include <iostream>
#include <ctime>
#include <iomanip>
using namespace std;

bool findIndices(const int A[8][15], int n, int m,
                 int& max_i, int& max_j, int& min_i, int& min_j)
{
    bool found = false;
    int max = 0;
    int min = 1000;
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < m; j++) {
            if (A[i][j] != 0) {
                found = true;
                if (A[i][j] > max) {
                    max_i = i;
                    max_j = j;
                    max = A[i][j];
                }
                if (A[i][j] < min) {
                    min_i = i;
                    min_j = j;
                    min = A[i][j];
                }
            }
        }
    }

    return found;
}

int main()
{
    srand(time(0));
    int n, m;
    int A[8][15];

    cout << "Enter n and m (n <= 8, m <= 15): ";
    cin >> n >> m;

    if (n < 1 || n > 8 || m < 1 || m > 15) {
        cout << "Invalid matrix size" << endl;
        return 0;
    }

    for (int i = 0; i < n; i++) {
        for (int j = 0; j < m; j++) {
            A[i][j] = rand() % 51 - 20;
            cout << setw(3) << A[i][j] << " ";
        }
        cout << endl;
    }

    int max_i, max_j, min_i, min_j;
    bool found = findIndices(A, n, m, max_i, max_j, min_i, min_j);

    if (!found) {
        cout << "No non-zero elements" << endl;
    } else {
        cout << "Max indexes: " << max_i+1 << " " << max_j+1 << endl;
        cout << "Min indexes: " << min_i+1 << " " << min_j+1 << endl;
        cout << "Difference: " << max_i - min_i << " " << max_j - min_j << endl;
    }

    return 0;
}
