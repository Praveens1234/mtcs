import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: const ColorScheme.dark(
        primary: Color(0xFF6366f1), // Indigo 500
        secondary: Color(0xFF10b981), // Emerald 500
        surface: Color(0xFF1e293b), // Slate 800
        error: Color(0xFFef4444), // Red 500
        onPrimary: Colors.white,
      ),
      scaffoldBackgroundColor: const Color(0xFF0f172a),
      cardColor: const Color(0xFF1e293b),
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFF0f172a),
        elevation: 0,
        centerTitle: true,
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: Color(0xFF1e293b),
        selectedItemColor: Color(0xFF6366f1),
        unselectedItemColor: Colors.grey,
        type: BottomNavigationBarType.fixed,
      ),
      textTheme: GoogleFonts.interTextTheme(ThemeData.dark().textTheme),
    );
  }

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: const ColorScheme.light(
        primary: Color(0xFF4f46e5), // Indigo 600
        secondary: Color(0xFF059669), // Emerald 600
        surface: Colors.white,
        error: Color(0xFFdc2626), // Red 600
        onPrimary: Colors.white,
      ),
      scaffoldBackgroundColor: const Color(0xFFf8fafc),
      cardColor: Colors.white,
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFFf8fafc),
        elevation: 0,
        centerTitle: true,
        foregroundColor: Colors.black,
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: Colors.white,
        selectedItemColor: Color(0xFF4f46e5),
        unselectedItemColor: Colors.grey,
        type: BottomNavigationBarType.fixed,
      ),
      textTheme: GoogleFonts.interTextTheme(ThemeData.light().textTheme),
    );
  }
}
