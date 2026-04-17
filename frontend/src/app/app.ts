import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-root',
  standalone: true,
  templateUrl: './app.html',
  styleUrls: ['./app.css']
})
export class AppComponent {

  machine = "";
  result: any;

  constructor(private http: HttpClient) {}

  calculate() {
    this.http.post("http://backend:5000/calculate", {
      machine: this.machine
    }).subscribe(res => {
      this.result = res;
    });
  }
}
