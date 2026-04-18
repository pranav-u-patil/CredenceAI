package com.CredenAI.hack;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.List;
import java.util.Map;

@Service
public class GeminiService {

    @Value("${gemini.api.key}")
    private String apiKey;

    @Value("${gemini.api.url}")
    private String apiUrl;

    public String analyzeClaim(String text) {
        RestTemplate restTemplate = new RestTemplate();

        // Ensure the URL is correctly formatted
        String fullUrl = apiUrl + "?key=" + apiKey;

        // Structure the request according to Google's API spec
        Map<String, Object> requestBody = Map.of(
                "contents", List.of(
                        Map.of("parts", List.of(
                                Map.of("text", "You are a fact-checker. Analyze this: " + text)
                        ))
                )
        );

        try {
            // Post the request
            Map<String, Object> response = restTemplate.postForObject(fullUrl, requestBody, Map.class);

            // Extract the actual text from the complex nested JSON response
            // Path: candidates[0] -> content -> parts[0] -> text
            List candidates = (List) response.get("candidates");
            Map firstCandidate = (Map) candidates.get(0);
            Map content = (Map) firstCandidate.get("content");
            List parts = (List) content.get("parts");
            Map firstPart = (Map) parts.get(0);

            return (String) firstPart.get("text");

        } catch (Exception e) {
            System.err.println("API Error: " + e.getMessage());
            return "Error: Could not reach Gemini. Check your URL and API Key.";
        }
    }
}