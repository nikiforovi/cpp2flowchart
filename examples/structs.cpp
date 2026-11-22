#include <iostream>

using namespace std;

struct Node {
    int data;
    Node* next;
};

struct Stack {
    Node* top;
    size_t size;

    void push(int val) {
        Node* newNode = new Node{val, nullptr};
        newNode->next = top;
        top = newNode;
        ++size;
    }

    int pop() {
        if (top == nullptr) {
            cout << "Error: stack underflow" << endl;
            return 0;
        }
        else {
            Node* temp = top;
            int data = temp->data;
            top = top->next;
            delete temp;
            --size;
            return data;
        }
    }
};

int main() {
    int in = -1;
    cout << "Input integers with Enters (0 - exit):" << endl;
    Stack* stack = new Stack{nullptr, 0};
    int counter = 0;
    while (in != 0) {
        cin >> in;
        counter++;
        stack->push(in);
        if (counter % 2 == 0) {
            int in2 = stack->pop();
            int in1 = stack->pop();
            int sum = in1+in2;
            cout << "Sum of 2 prev integers: " << sum << endl;
            stack->push(in1);
            stack->push(in2);
            stack->push(sum);
        }
    }
    cout << "Stack:" << endl;
    while (stack->size != 0) {
        cout << stack->pop() << ' ';
    }
    delete stack;
    return 0;
}
