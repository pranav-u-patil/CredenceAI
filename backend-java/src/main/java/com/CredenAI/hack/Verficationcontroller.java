package com.CredenAI.hack;

import  com.CredenAI.hack.RequestPayload;
import com.CredenAI.hack.ResponsePayload;
import com.CredenAI.hack.AgentService;
import com.CredenAI.hack.GeminiService;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@CrossOrigin(origins = "*")
public class Verficationcontroller {

    @Autowired
    private GeminiService geminiService;

    @Autowired
    private AgentService agentService;
    @GetMapping("/test")
    public String test(){
        return "working";
    }
    @PostMapping("/verify")
    public ResponsePayload verify(@RequestBody RequestPayload request) {

        String geminiResponse = geminiService.analyzeClaim(request.getText());

        System.out.println("Gemini Raw Response: " + geminiResponse);

        String finalDecision = agentService.processLLMResponse(geminiResponse);

        return new ResponsePayload(finalDecision);
    }
}