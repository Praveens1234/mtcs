import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_client_sse/flutter_client_sse.dart';
import 'package:flutter_client_sse/constants/sse_request_type_enum.dart';

class ApiService {
  // Use a default local IP for emulator testing or let user configure
  static String baseUrl = "http://10.0.2.2:9600";

  static void setBaseUrl(String url) {
    baseUrl = url;
  }

  // HTTP GET
  static Future<dynamic> get(String endpoint) async {
    try {
      final response = await http.get(Uri.parse('$baseUrl$endpoint'));
      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to load data: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('API Error: $e');
    }
  }

  // HTTP POST
  static Future<dynamic> post(String endpoint, Map<String, dynamic> body) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl$endpoint'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode(body),
      );
      if (response.statusCode >= 200 && response.statusCode < 300) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to post data: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('API Error: $e');
    }
  }

  // SSE Stream
  static Stream<SSEModel> getSseStream(String endpoint) {
    return SSEClient.subscribeToSSE(
      method: SSERequestType.GET,
      url: '$baseUrl$endpoint',
      header: {
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache",
      },
    );
  }

  static void unsubscribeSse() {
    SSEClient.unsubscribeFromSSE();
  }
}
