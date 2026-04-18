package com.CredenAI.hack;

import org.springframework.stereotype.Service;

@Service
public class AgentService {

    public String processLLMResponse(String llmResponse) {

        if (llmResponse == null || llmResponse.isEmpty()) {
            return "Error: No response from Gemini AI";
        }

        String response = llmResponse.toLowerCase();

        if (response.contains("false") || response.contains("fake")) {
            return "High Risk: The claim appears to be misleading or false.";
        }

        if (response.contains("unverified") || response.contains("uncertain")) {
            return "Medium Risk: The claim needs further verification.";
        }

        if (response.contains("true") || response.contains("verified")) {
            return "Low Risk: The claim appears credible.";
        }

        return "Unknown Risk: Unable to determine credibility.";
    }
}
